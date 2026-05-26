# -*- coding: utf-8 -*-
"""Tách đơn nghỉ theo quy tắc tháng: P1 (ngày 1) → P2 (ngày 2–3) → O (từ ngày 4)."""

import logging
import uuid
from datetime import timedelta

from odoo import api, fields, models

_SKIP_RESPONSIBLE_SUBMIT_NOTIFY_CTX = "skip_responsible_submit_notify"

_logger = logging.getLogger(__name__)

_SKIP_MONTHLY_MIEN_SPLIT_CTX = "skip_monthly_mien_split"


class HrLeaveMonthlySplit(models.Model):
    _inherit = "hr.leave"

    monthly_leave_split_preview = fields.Text(
        string="Phân tích ngày nghỉ trong đơn",
        readonly=True,
    )

    @api.model
    def _format_split_preview_date(self, value):
        d = self._coerce_to_date(value)
        return d.strftime("%d/%m/%Y") if d else ""

    def _format_split_preview_date_range(self, date_from, date_to):
        start = self._format_split_preview_date(date_from)
        end = self._format_split_preview_date(date_to)
        if not start:
            return ""
        if start == end:
            return start
        return f"{start} -> {end}"

    def _build_monthly_leave_split_preview_text(self):
        self.ensure_one()
        if (
            not self.employee_id
            or not self.request_date_from
            or not self.request_date_to
            or not self._monthly_p1p2_mien_applies(self.employee_id)
        ):
            return False
        if self.request_date_from > self.request_date_to:
            return False
        total_days = (self.request_date_to - self.request_date_from).days + 1
        if total_days <= 1:
            return False
        exclude = [self.id] if self.id else []
        days_before = self._count_leave_days_in_calendar_month(
            self.employee_id,
            self.request_date_from.year,
            self.request_date_from.month,
            exclude,
        )
        plan = self._monthly_mien_split_plan(
            days_before, self.request_date_from, self.request_date_to
        )
        if len(plan) <= 1:
            return False
        lines = []
        for kind, seg_from, seg_to in plan:
            leave_type = self._monthly_mien_leave_type_for_kind(kind)
            label = leave_type.name if leave_type else kind.upper()
            dates = self._format_split_preview_date_range(seg_from, seg_to)
            num_days = (seg_to - seg_from).days + 1
            lines.append(f"{label} ({dates}) — {num_days} ngày")
        return "\n".join(lines)

    def _refresh_monthly_leave_split_preview(self):
        try:
            text = self._build_monthly_leave_split_preview_text()
            self.monthly_leave_split_preview = text or False
        except Exception:
            _logger.exception("monthly_leave_split_preview failed")
            self.monthly_leave_split_preview = False

    def _monthly_mien_split_plan(self, days_before, date_from, date_to):
        """
        Trả về list (kind, date_from, date_to) với kind in ('p1', 'p2', 'o').
        days_before: số ngày nghỉ đã có trong tháng (không tính đơn hiện tại).
        """
        from .hr_leave_mien_config import MAX_PAID_LEAVE_DAYS_PER_MONTH

        segments = []
        cursor = date_from
        remaining = (date_to - date_from).days + 1

        if days_before == 0 and remaining > 0:
            segments.append(("p1", cursor, cursor))
            cursor += timedelta(days=1)
            remaining -= 1
            days_before += 1

        p2_budget = max(0, MAX_PAID_LEAVE_DAYS_PER_MONTH - days_before)
        p2_days = min(p2_budget, remaining)
        if p2_days > 0:
            p2_end = cursor + timedelta(days=p2_days - 1)
            segments.append(("p2", cursor, p2_end))
            cursor = p2_end + timedelta(days=1)
            remaining -= p2_days

        if remaining > 0:
            segments.append(("o", cursor, date_to))

        return segments

    def _monthly_mien_should_split(self, leave):
        if self.env.context.get(_SKIP_MONTHLY_MIEN_SPLIT_CTX):
            return False
        if not leave.employee_id or not leave.request_date_from or not leave.request_date_to:
            return False
        if not self._monthly_p1p2_mien_applies(leave.employee_id):
            return False
        exclude = [leave.id] if leave.id else []
        days_before = self._count_leave_days_in_calendar_month(
            leave.employee_id,
            leave.request_date_from.year,
            leave.request_date_from.month,
            exclude,
        )
        plan = self._monthly_mien_split_plan(
            days_before, leave.request_date_from, leave.request_date_to
        )
        return len(plan) > 1

    def _monthly_mien_leave_type_for_kind(self, kind, selected=None):
        if kind == "p1":
            return self._get_p1_leave_type(selected)
        if kind == "p2":
            return self._get_p2_leave_type(selected)
        if kind == "o":
            return self._get_o_leave_type(selected)
        return self.env["hr.leave.type"]

    def _monthly_mien_make_companion_vals(self, leave, leave_type, date_from, date_to, group_id):
        vals = {
            "employee_id": leave.employee_id.id,
            "holiday_status_id": leave_type.id,
            "request_date_from": date_from,
            "request_date_to": date_to,
            "name": leave.name or "",
            "state": leave.state,
        }
        if "split_group_id" in leave._fields:
            vals["split_group_id"] = group_id
        if leave.department_id:
            vals["department_id"] = leave.department_id.id
        return vals

    def _monthly_mien_do_split(self, leave):
        exclude = [leave.id] if leave.id else []
        days_before = self._count_leave_days_in_calendar_month(
            leave.employee_id,
            leave.request_date_from.year,
            leave.request_date_from.month,
            exclude,
        )
        plan = self._monthly_mien_split_plan(
            days_before, leave.request_date_from, leave.request_date_to
        )
        if len(plan) <= 1:
            return

        group_id = (
            leave.split_group_id
            if "split_group_id" in leave._fields and leave.split_group_id
            else str(uuid.uuid4())
        )
        first_kind, first_from, first_to = plan[0]
        first_type = self._monthly_mien_leave_type_for_kind(first_kind)
        if not first_type:
            _logger.warning(
                "monthly_mien_split: missing leave type %s for leave %s",
                first_kind,
                leave.id,
            )
            return

        write_vals = {
            "holiday_status_id": first_type.id,
            "request_date_from": first_from,
            "request_date_to": first_to,
        }
        if "split_group_id" in leave._fields:
            write_vals["split_group_id"] = group_id
        leave.with_context(leave_skip_state_check=True).write(write_vals)

        companions = []
        for kind, seg_from, seg_to in plan[1:]:
            lt = self._monthly_mien_leave_type_for_kind(kind)
            if not lt:
                _logger.warning(
                    "monthly_mien_split: missing leave type %s — skip segment",
                    kind,
                )
                continue
            companions.append(
                self._monthly_mien_make_companion_vals(
                    leave, lt, seg_from, seg_to, group_id
                )
            )

        if companions:
            create_ctx = {
                _SKIP_MONTHLY_MIEN_SPLIT_CTX: True,
                "leave_fast_create": True,
                "mail_activity_automation_skip": True,
                _SKIP_RESPONSIBLE_SUBMIT_NOTIFY_CTX: True,
            }
            Leave = self.with_context(**create_ctx)
            for companion_vals in companions:
                Leave.create([companion_vals])

        if hasattr(leave, "_notify_split_group_after_companion_create"):
            leave._notify_split_group_after_companion_create()

        _logger.info(
            "monthly_mien_split: leave %s → %s segments (days_before=%s)",
            leave.id,
            len(plan),
            days_before,
        )
