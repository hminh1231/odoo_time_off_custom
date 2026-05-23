"""Auto-split P1 → P2 for CHT / ASM / RSM when con_lai == 1 and request > 1 day.

When an eligible employee (job title in _P1P2_JOB_TITLES) creates a leave of
type P1 and their remaining balance (con_lai) is exactly 1, but they request
more than 1 day, the system automatically:

  1. Trims the original record to cover only the first day (P1 type).
  2. Creates a companion record for the remaining days using the P2 leave type.

The two records are linked via p2_leave_id / p1_leave_id. Refusing or
resetting either record cascades to its companion so they stay in sync.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

# Job title keys (lowercase) whose leaves are eligible for P1→P2 auto-split.
_P1P2_JOB_TITLES = frozenset({"cửa hàng trưởng", "asm", "rsm"})

# Context key to prevent re-entrant split when creating the P2 companion.
_SKIP_P1P2_SPLIT_CTX = "skip_p1p2_auto_split"

# Leave type names used to locate P1 and P2 in the database.
_P1_LEAVE_TYPE_NAME = "Nghỉ phép (P1)"
_P2_LEAVE_TYPE_NAME = "Nghỉ phép (P2) - Ngày nghỉ kế tiếp trong tháng"


class HrLeaveP1P2Split(models.Model):
    _inherit = "hr.leave"

    # Link from P1 → its P2 companion
    p2_leave_id = fields.Many2one(
        "hr.leave",
        string="Đơn P2 kèm theo",
        ondelete="set null",
        copy=False,
        readonly=True,
    )
    # Link from P2 → its originating P1
    p1_leave_id = fields.Many2one(
        "hr.leave",
        string="Đơn P1 gốc",
        ondelete="set null",
        copy=False,
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _p1p2_find_leave_type(self, name):
        """Return the hr.leave.type with the given name, or empty recordset."""
        lt = self.env["hr.leave.type"].sudo().search([("name", "=", name)], limit=1)
        if not lt:
            _logger.warning("p1p2_split: leave type not found: %r", name)
        return lt

    def _p1p2_employee_job_title(self, employee):
        return (employee.job_title or "").strip().lower()

    def _p1p2_should_split(self, leave):
        """Return True when this leave must be split into P1 + P2."""
        if self.env.context.get(_SKIP_P1P2_SPLIT_CTX):
            return False
        emp = leave.employee_id
        if not emp:
            return False
        if self._p1p2_employee_job_title(emp) not in _P1P2_JOB_TITLES:
            return False
        p1_type = self._p1p2_find_leave_type(_P1_LEAVE_TYPE_NAME)
        if not p1_type or leave.holiday_status_id.id != p1_type.id:
            return False
        con_lai = emp.sudo().con_lai or 0
        if con_lai != 1:
            return False
        if leave.number_of_days <= 1:
            return False
        return True

    # ------------------------------------------------------------------
    # Create — spawn P2 companion when conditions are met
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self.env.context.get(_SKIP_P1P2_SPLIT_CTX):
            return records
        for leave in records:
            if not self._p1p2_should_split(leave):
                continue
            self._p1p2_do_split(leave)
        return records

    def _p1p2_do_split(self, leave):
        """Trim leave to day 1 (P1) and create a companion P2 for remaining days."""
        p2_type = self._p1p2_find_leave_type(_P2_LEAVE_TYPE_NAME)
        if not p2_type:
            _logger.warning(
                "p1p2_split: cannot split leave %s — P2 leave type not found", leave.id
            )
            return

        original_date_to = leave.request_date_to

        # Shrink the P1 leave to exactly 1 day (keep date_from, set date_to = date_from).
        p1_date_from = leave.request_date_from
        p1_date_to = p1_date_from  # 1 day only

        # P2 covers day 2 onward.
        p2_date_from = p1_date_from + timedelta(days=1)
        p2_date_to = original_date_to

        if p2_date_from > p2_date_to:
            # Shouldn't happen given number_of_days > 1 check, but guard anyway.
            return

        # Update P1 record to 1 day.
        leave.with_context(leave_skip_state_check=True).write({
            "request_date_to": p1_date_to,
        })

        # Build P2 vals from P1 — copy essential fields.
        p2_vals = {
            "employee_id": leave.employee_id.id,
            "holiday_status_id": p2_type.id,
            "request_date_from": p2_date_from,
            "request_date_to": p2_date_to,
            "name": leave.name or "",
            "state": leave.state,
            "p1_leave_id": leave.id,
        }
        if leave.department_id:
            p2_vals["department_id"] = leave.department_id.id

        p2 = self.with_context(
            **{
                _SKIP_P1P2_SPLIT_CTX: True,
                "leave_fast_create": True,
                "mail_activity_automation_skip": True,
            }
        ).create([p2_vals])

        # Link P1 → P2.
        leave.write({"p2_leave_id": p2.id})

        _logger.info(
            "p1p2_split: split leave %s (P1, %s–%s) + companion %s (P2, %s–%s) for employee %s",
            leave.id, p1_date_from, p1_date_to,
            p2.id, p2_date_from, p2_date_to,
            leave.employee_id.name,
        )

    # ------------------------------------------------------------------
    # Cascade refuse to companion
    # ------------------------------------------------------------------

    def action_refuse(self, reason=False):
        res = super().action_refuse(reason=reason)
        for leave in self:
            companion = leave.p2_leave_id or leave.p1_leave_id
            if companion and companion.state not in ("refuse", "draft"):
                try:
                    companion.with_context(
                        skip_p1p2_cascade=True
                    ).action_refuse(reason=reason or _("Từ chối theo đơn liên kết"))
                except (UserError, Exception):
                    _logger.warning(
                        "p1p2_split: could not refuse companion leave %s", companion.id
                    )
        return res

    # ------------------------------------------------------------------
    # Cascade reset to draft to companion
    # ------------------------------------------------------------------

    def action_draft(self):
        res = super().action_draft()
        for leave in self:
            if self.env.context.get("skip_p1p2_cascade"):
                continue
            companion = leave.p2_leave_id or leave.p1_leave_id
            if companion and companion.state == "refuse":
                try:
                    companion.with_context(skip_p1p2_cascade=True).action_draft()
                except (UserError, Exception):
                    _logger.warning(
                        "p1p2_split: could not reset companion leave %s to draft", companion.id
                    )
        return res

    # ------------------------------------------------------------------
    # Cascade unlink to companion
    # ------------------------------------------------------------------

    def unlink(self):
        companions = self.env["hr.leave"]
        for leave in self:
            if self.env.context.get("skip_p1p2_cascade"):
                continue
            companion = leave.p2_leave_id or leave.p1_leave_id
            if companion:
                companions |= companion
        # Detach links first to avoid FK cascade loops.
        self.write({"p2_leave_id": False, "p1_leave_id": False})
        res = super().unlink()
        if companions:
            companions.with_context(skip_p1p2_cascade=True).write(
                {"p2_leave_id": False, "p1_leave_id": False}
            )
            try:
                companions.with_context(skip_p1p2_cascade=True).unlink()
            except (UserError, Exception):
                _logger.warning(
                    "p1p2_split: could not unlink companion leaves %s", companions.ids
                )
        return res
