"""Auto-split P1/P2/O for CHT / ASM / RSM when requesting > 1 day.

Rules (always triggered when job title is eligible + leave type is P1 + days > 1):

  Case A — con_lai >= requested days:
    Day 1          → P1  (1 day)
    Days 2..end    → P2  (remaining days)

  Case B — con_lai < requested days (but con_lai >= 1, enforced by balance check):
    Day 1                      → P1  (1 day)
    Days 2..(con_lai)          → P2  (con_lai - 1 days, may be 0 → skipped)
    Days (con_lai+1)..end      → O   (requested - con_lai days)

Example: con_lai=3, requested=4  →  1 P1 + 2 P2 + 1 O
Example: con_lai=5, requested=3  →  1 P1 + 2 P2

All companion records are linked back to the originating P1 via
split_group_id (a UUID stored as Char) so cascades (refuse/draft/unlink)
can propagate to the whole group regardless of how many pieces exist.
"""

import logging
import uuid
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

_SKIP_RESPONSIBLE_SUBMIT_NOTIFY_CTX = "skip_responsible_submit_notify"

_logger = logging.getLogger(__name__)

# Job title keys (lowercase) whose leaves are eligible for auto-split.
_P1P2_JOB_TITLES = frozenset({"cửa hàng trưởng", "asm", "rsm"})

# Context key to prevent re-entrant split when creating companion records.
_SKIP_P1P2_SPLIT_CTX = "skip_p1p2_auto_split"

# Leave type names — must match exactly what is configured in Odoo.
_P1_LEAVE_TYPE_NAME = "Nghỉ phép (P1)"
_P2_LEAVE_TYPE_NAME = "Nghỉ phép (P2) - Ngày nghỉ kế tiếp trong tháng"
_O_LEAVE_TYPE_NAME = "Nghỉ không lương (O)"


class HrLeaveP1P2Split(models.Model):
    _inherit = "hr.leave"

    # UUID shared by all records that were split from the same original request.
    split_group_id = fields.Char(
        string="Split Group",
        copy=False,
        readonly=True,
        index=True,
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _p1p2_find_leave_type(self, name):
        lt = self.env["hr.leave.type"].sudo().search([("name", "=", name)], limit=1)
        if not lt:
            _logger.warning("p1p2_split: leave type not found: %r", name)
        return lt

    def _p1p2_should_split(self, leave):
        """Return True when this leave must be auto-split."""
        if self.env.context.get(_SKIP_P1P2_SPLIT_CTX):
            return False
        emp = leave.employee_id
        if not emp:
            return False
        if (emp.job_title or "").strip().lower() not in _P1P2_JOB_TITLES:
            return False
        p1_type = self._p1p2_find_leave_type(_P1_LEAVE_TYPE_NAME)
        if not p1_type or leave.holiday_status_id.id != p1_type.id:
            return False
        if leave.number_of_days <= 1:
            return False
        return True

    def _p1p2_get_companions(self):
        """Return all other leaves in the same split group."""
        self.ensure_one()
        if not self.split_group_id:
            return self.env["hr.leave"]
        return self.env["hr.leave"].search([
            ("split_group_id", "=", self.split_group_id),
            ("id", "!=", self.id),
        ])

    def _p1p2_make_companion_vals(self, leave, leave_type, date_from, date_to, group_id):
        vals = {
            "employee_id": leave.employee_id.id,
            "holiday_status_id": leave_type.id,
            "request_date_from": date_from,
            "request_date_to": date_to,
            "name": leave.name or "",
            "state": leave.state,
            "split_group_id": group_id,
        }
        if leave.department_id:
            vals["department_id"] = leave.department_id.id
        return vals

    # ------------------------------------------------------------------
    # Create — perform the split
    # ------------------------------------------------------------------

    def _p1p2_any_will_split_vals_list(self, vals_list):
        if self.env.context.get(_SKIP_P1P2_SPLIT_CTX):
            return False
        Leave = self.env["hr.leave"]
        for vals in vals_list:
            probe = Leave.new(dict(vals))
            if Leave._p1p2_should_split(probe):
                return True
        return False

    @api.model_create_multi
    def create(self, vals_list):
        ctx = dict(self.env.context)
        if self._p1p2_any_will_split_vals_list(vals_list):
            ctx[_SKIP_RESPONSIBLE_SUBMIT_NOTIFY_CTX] = True
        records = super(HrLeaveP1P2Split, self.with_context(ctx)).create(vals_list)
        if self.env.context.get(_SKIP_P1P2_SPLIT_CTX):
            return records
        for leave in records:
            if self._p1p2_should_split(leave):
                self._p1p2_do_split(leave)
        return records

    def _p1p2_do_split(self, leave):
        emp = leave.employee_id.sudo()
        con_lai = int(emp.con_lai or 0)           # available days (integer)
        requested = int(leave.number_of_days)     # total days requested

        p2_type = self._p1p2_find_leave_type(_P2_LEAVE_TYPE_NAME)
        o_type = self._p1p2_find_leave_type(_O_LEAVE_TYPE_NAME)

        if not p2_type:
            _logger.warning("p1p2_split: P2 leave type not found — aborting split for leave %s", leave.id)
            return

        group_id = str(uuid.uuid4())
        date_cursor = leave.request_date_from
        original_date_to = leave.request_date_to
        companions_vals = []

        # --- Day 1: P1 (always 1 day, shrink the original record) ---
        p1_date_to = date_cursor           # inclusive
        date_cursor = date_cursor + timedelta(days=1)

        # --- Days 2..con_lai: P2 ---
        p2_days = min(con_lai - 1, requested - 1)   # days 2..min(con_lai, requested)
        if p2_days > 0 and p2_type:
            p2_date_from = date_cursor
            p2_date_to = date_cursor + timedelta(days=p2_days - 1)
            companions_vals.append(
                self._p1p2_make_companion_vals(leave, p2_type, p2_date_from, p2_date_to, group_id)
            )
            date_cursor = p2_date_to + timedelta(days=1)

        # --- Remaining days beyond con_lai: O ---
        o_days = requested - con_lai
        if o_days > 0 and o_type:
            o_date_from = date_cursor
            o_date_to = original_date_to
            companions_vals.append(
                self._p1p2_make_companion_vals(leave, o_type, o_date_from, o_date_to, group_id)
            )
        elif o_days > 0 and not o_type:
            _logger.warning("p1p2_split: O leave type not found — O segment skipped for leave %s", leave.id)

        # Shrink original to P1 (1 day) and stamp the group id.
        leave.with_context(leave_skip_state_check=True).write({
            "request_date_to": p1_date_to,
            "split_group_id": group_id,
        })

        # Create all companion records (skip per-segment approver notify; ping once below).
        if companions_vals:
            self.with_context(**{
                _SKIP_P1P2_SPLIT_CTX: True,
                "leave_fast_create": True,
                "mail_activity_automation_skip": True,
                _SKIP_RESPONSIBLE_SUBMIT_NOTIFY_CTX: True,
            }).create(companions_vals)

        if hasattr(leave, "_notify_split_group_after_companion_create"):
            leave._notify_split_group_after_companion_create()

        _logger.info(
            "p1p2_split: leave %s → 1 P1 + %s P2 + %s O (con_lai=%s, requested=%s, employee=%s)",
            leave.id, p2_days, max(o_days, 0), con_lai, requested, emp.name,
        )

    # ------------------------------------------------------------------
    # Cascade: refuse
    # ------------------------------------------------------------------

    def action_refuse(self, reason=False):
        res = super().action_refuse(reason=reason)
        if self.env.context.get("skip_p1p2_cascade"):
            return res
        for leave in self:
            companions = leave._p1p2_get_companions()
            active = companions.filtered(lambda l: l.state not in ("refuse", "draft"))
            if active:
                try:
                    active.with_context(skip_p1p2_cascade=True).action_refuse(
                        reason=reason or _("Từ chối theo đơn liên kết")
                    )
                except (UserError, Exception):
                    _logger.warning("p1p2_split: could not refuse companions %s", active.ids)
        return res

    # ------------------------------------------------------------------
    # Cascade: reset to draft
    # ------------------------------------------------------------------

    def action_draft(self):
        res = super().action_draft()
        if self.env.context.get("skip_p1p2_cascade"):
            return res
        for leave in self:
            companions = leave._p1p2_get_companions()
            refused = companions.filtered(lambda l: l.state == "refuse")
            if refused:
                try:
                    refused.with_context(skip_p1p2_cascade=True).action_draft()
                except (UserError, Exception):
                    _logger.warning("p1p2_split: could not reset companions %s to draft", refused.ids)
        return res

    # ------------------------------------------------------------------
    # Cascade: unlink
    # ------------------------------------------------------------------

    def unlink(self):
        if self.env.context.get("skip_p1p2_cascade"):
            return super().unlink()
        companions = self.env["hr.leave"]
        for leave in self:
            companions |= leave._p1p2_get_companions()
        # Detach group links to avoid search finding them during cascade.
        (self | companions).with_context(leave_skip_state_check=True).write(
            {"split_group_id": False}
        )
        res = super().unlink()
        if companions:
            try:
                companions.with_context(skip_p1p2_cascade=True).unlink()
            except (UserError, Exception):
                _logger.warning("p1p2_split: could not unlink companions %s", companions.ids)
        return res
