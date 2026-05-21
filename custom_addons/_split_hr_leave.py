# -*- coding: utf-8 -*-
"""Split time_off_extra_approval/models/hr_leave.py into three module extensions."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "time_off_extra_approval" / "models" / "hr_leave.py"

OUT = {
    "handover": ROOT / "time_off_work_handover" / "models" / "hr_leave.py",
    "approval": ROOT / "time_off_responsible_approval" / "models" / "hr_leave.py",
    "core": ROOT / "time_off_extra_approval" / "models" / "hr_leave.py",
}

HANDOVER_METHODS = {
    "_compute_can_skip_work_handover",
    "_get_effective_employee_for_skip_handover",
    "_read_job_title_safely",
    "_can_skip_workover_rank_for_employee",
    "_can_skip_work_handover_by_job_title",
    "_check_skip_work_handover_permission",
    "_check_handover_employee_limit",
    "_check_handover_duplicate_recipients",
    "_check_handover_content_required_on_submit",
    "_check_handover_required_on_submit",
    "_get_requested_interval",
    "_get_unavailable_handover_employees",
    "_compute_unavailable_handover_employee_ids",
    "_check_handover_employee_availability",
    "_onchange_handover_employee_availability",
    "_onchange_handover_acceptance_ids",
    "_resequence_handover_acceptance_lines",
    "_sync_handover_employees_from_acceptance",
    "_compute_can_respond_handover",
    "_compute_handover_waiting_label",
    "_compute_handover_refused_label",
    "_compute_handover_refusal_reason_label",
    "_compute_handover_refused_recipient_ids",
    "_compute_handover_replaceable_recipient_ids",
    "_compute_handover_escalation_label",
    "_compute_handover_escalation_pick_prompt",
    "_compute_handover_assigned_recipient_banner",
    "_compute_handover_recipient_list_readonly",
    "_compute_handover_sheet_hidden_for_viewer",
    "_compute_can_manage_handover_replacement",
    "_bootstrap_handover_workflow",
    "_sync_handover_acceptance_lines",
    "_handover_employee_for_assigner_user",
    "_handover_format_job_name_from_employee",
    "_handover_format_job_name_from_user",
    "_handover_who_label_for_line",
    "_handover_is_bp_handover_assignment",
    "_handover_activity_note_for_line",
    "_refresh_handover_activity_notes_for_employees",
    "_mark_pending_handover_lines_as_escalation_assigned",
    "_schedule_work_handover_activities",
    "_mark_handover_requested_at",
    "_get_org_chart_department_head_user",
    "_get_org_chart_department_manager_user_from_user",
    "_get_next_manager_user_from_user",
    "_notify_requester_handover_escalation_started_via_bot",
    "_notify_handover_timeout_escalation",
    "_notify_handover_bot_leave_form_open_button_markup",
    "_notify_specific_handover_recipients_via_bot",
    "_notify_handover_recipients_submit_via_bot",
    "_handover_owner_selected_replacement",
    "_feedback_all_work_handover_activities",
    "_notify_requester_handover_refusal",
    "_notify_requester_handover_refusal_via_bot",
    "_notify_requester_handover_complete_via_bot",
    "_feedback_requester_handover_update_todo",
    "_get_handover_blocking_employees",
    "_handover_past_due_without_any_acceptance",
    "_handover_escalation_after_hours",
    "_handover_second_escalation_hours",
    "_handover_max_escalation_job_title",
    "_handover_job_title_rank",
    "_get_handover_escalation_cap_user_for_max_title",
    "_handover_is_max_escalation_reached",
    "_handover_should_auto_cancel_at_max_level",
    "_handover_cancel_after_max_hours",
    "_current_user_escalation_assigned_handover_recipient_line",
    "_current_user_is_pending_handover_recipient",
    "_viewer_can_manage_handover_acceptance_sheet",
    "_handover_ready_for_approval",
    "_ensure_handover_ready_for_approval",
    "action_handover_accept",
    "action_handover_refuse",
    "action_handover_refuse_with_reason",
    "action_handover_replacement_yes",
    "action_handover_replacement_no",
    "action_handover_apply_replacement",
    "cron_escalate_handover_timeouts",
    "_apply_handover_timeout_escalation",
    "_apply_handover_timeout_escalation_to_department_manager",
    "_apply_handover_timeout_cancel_at_max_level",
    "_handover_write_before",
    "_handover_write_after",
    "action_confirm",
    "create",
}

APPROVAL_METHODS = {
    "_get_employee_responsible_users",
    "_get_leave_employee_department_for_approval",
    "_get_leave_department_manager_user",
    "_employee_hr_substitute_final_director_with_department_manager",
    "_get_org_chart_approver_users_ordered",
    "_employee_hr_responsible_users_core",
    "_get_company_director_users",
    "_get_configured_director_order_users",
    "_employee_hr_expanded_director_suffix_users",
    "_is_special_parallel_directors_leave",
    "_is_multi_director_special_employee",
    "_employee_hr_maybe_expand_multi_director",
    "_employee_hr_chain_contains_director",
    "_responsible_pending_current_wave",
    "_build_responsible_approval_sequences",
    "_get_responsible_approval_users",
    "_sort_responsible_users_by_job_title",
    "_employee_hr_blocks_self_approval_non_director",
    "_get_multi_step_approvers",
    "_multi_step_previous_steps_logged",
    "_compute_extra_approver_user_ids",
    "_compute_approval_actionable_user_ids",
    "_get_current_multi_step",
    "_init_responsible_approval_lines",
    "_ensure_responsible_approval_lines",
    "_responsible_backfill_pending_since_if_missing",
    "_notify_responsible_approvers_submission",
    "_notify_responsible_current_turn",
    "_format_approval_bot_date",
    "_get_approval_bot_leave_notification_details",
    "_notify_responsible_current_turn_via_approval_bot",
    "_notify_requester_approval_outcome_via_bot",
    "_bot_status_current_step_details",
    "_compute_can_multi_step_approve",
    "_compute_can_responsible_approve",
    "_compute_approval_current_step_label",
    "_is_extra_approver",
    "_get_responsible_for_approval",
    "action_multi_step_approve",
    "action_multi_step_refuse",
    "action_responsible_approve",
    "action_responsible_refuse",
    "action_open_multi_step_refuse_wizard",
    "action_open_responsible_refuse_wizard",
    "cron_escalate_responsible_approval_timeouts",
    "_apply_responsible_timeout_escalation",
    "_approval_write_before",
    "_approval_write_after",
    "action_confirm",
    "create",
}

CORE_METHODS = {
    "_register_hook",
    "_m2o_id",
    "_parse_date_val",
    "_required_lead_days_for_job_title",
    "_merge_vals_for_emergency_check",
    "_emergency_leave_violation_info",
    "_apply_emergency_leave_on_vals",
    "check_emergency_leave_lead_time",
    "_compute_emergency_leave_approver_notice",
    "_compute_status_display_label",
    "_leave_discuss_hmac_secret_key",
    "_leave_discuss_link_token",
    "_leave_discuss_link_verify_token",
    "_leave_discuss_open_client_fragment",
    "_leave_discuss_open_spa_path",
    "_leave_discuss_open_http_path",
    "_notify_discuss_leave_open_button_markup",
    "_notify_approval_bot_leave_form_open_button_markup",
    "_action_return_reload_leave_form",
    "_vals_trigger_emergency_leave_check",
    "write",
    "action_confirm",
    "_check_approval_update",
    "action_approve",
    "action_cancel",
    "action_open_refuse_wizard",
    "action_refuse",
    "_compute_can_approve",
    "_compute_can_validate",
    "_compute_can_refuse",
    "activity_update",
    "_notify_requester_auto_cancel_via_odoo_bot",
}

HANDOVER_FIELD_RE = re.compile(
    r"^\s+(handover_|skip_work_handover|can_skip_work_handover|unavailable_handover_)"
)
APPROVAL_FIELD_RE = re.compile(
    r"^\s+(multi_step_|multi_approval_|extra_approver_|approval_actionable_|"
    r"responsible_approval_|can_responsible_approve|can_multi_step_approve|approval_current_step_label)"
)

HEADERS = {
    "handover": '''# -*- coding: utf-8 -*-
import logging
import re
import unicodedata
from datetime import date, datetime, time, timedelta

from markupsafe import Markup, escape

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import sql
from odoo.tools.translate import _

from odoo.addons.time_off_work_handover import constants as handover_constants

_logger = logging.getLogger(__name__)

_HANDOVER_ACTIVITY_XMLID = handover_constants.HANDOVER_ACTIVITY_XMLID
_HANDOVER_ACTIVE_STATES = handover_constants.HANDOVER_ACTIVE_STATES
_TODO_ACTIVITY_XMLID = "mail.mail_activity_data_todo"
_HANDOVER_ESCALATION_MINUTES = handover_constants.HANDOVER_ESCALATION_MINUTES
_HANDOVER_ESCALATION_TO_MANAGER_HOURS = handover_constants.HANDOVER_ESCALATION_TO_MANAGER_HOURS
_DEPARTMENT_HEAD_JOB_TITLE_KEY = handover_constants.DEPARTMENT_HEAD_JOB_TITLE_KEY
_DEPARTMENT_MANAGER_JOB_TITLE_KEY = handover_constants.DEPARTMENT_MANAGER_JOB_TITLE_KEY
_SKIP_SUBMIT_BOT_NOTIFY_CTX = handover_constants.SKIP_SUBMIT_BOT_NOTIFY_CTX


class HrLeaveHandover(models.Model):
    _inherit = "hr.leave"

''',
    "approval": '''# -*- coding: utf-8 -*-
import logging
import re
import unicodedata
from datetime import date, datetime, time, timedelta

from markupsafe import Markup, escape

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _

from odoo.addons.hr_job_title_vn.models.hr_version import JOB_TITLE_SELECTION
from odoo.addons.time_off_responsible_approval import constants as approval_constants

_logger = logging.getLogger(__name__)

_MULTI_STEP_RESET_CTX = approval_constants.MULTI_STEP_RESET_CTX
_SKIP_OUTCOME_BOT_NOTIFY_CTX = approval_constants.SKIP_OUTCOME_BOT_NOTIFY_CTX
_SKIP_RESPONSIBLE_SUBMIT_NOTIFY_CTX = approval_constants.SKIP_RESPONSIBLE_SUBMIT_NOTIFY_CTX
_HR_RESPONSIBLE_APPROVAL_JOB_TITLE_ORDER = tuple(
    key for key, _label in JOB_TITLE_SELECTION if key != "nhân viên"
)
_DIRECTOR_JOB_TITLE_KEY = approval_constants.DIRECTOR_JOB_TITLE_KEY
_MAX_EMPLOYEE_HR_RESPONSIBLES = approval_constants.MAX_EMPLOYEE_HR_RESPONSIBLES
_MAX_EMPLOYEE_HR_RESPONSIBLES_MULTI_DIRECTOR = approval_constants.MAX_EMPLOYEE_HR_RESPONSIBLES_MULTI_DIRECTOR


def _job_title_approval_sort_key(user, order_index):
    title = user.employee_id.job_title if user.employee_id else False
    if title and title in order_index:
        return (order_index[title], user.id)
    return (len(order_index) + 1, user.id)


def _normalize_job_title_key(title):
    normalized = (title or "").strip().casefold()
    normalized = "".join(
        ch for ch in unicodedata.normalize("NFKD", normalized) if not unicodedata.combining(ch)
    )
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    aliases = {"truong bp": "truong bo phan"}
    return aliases.get(normalized, normalized)


def _job_title_rank_map():
    rank_map = {}
    for idx, (key, label) in enumerate(JOB_TITLE_SELECTION):
        rank_map[_normalize_job_title_key(key)] = idx
        rank_map[_normalize_job_title_key(label)] = idx
    return rank_map


class HrLeaveResponsibleApproval(models.Model):
    _inherit = "hr.leave"

''',
    "core": '''# -*- coding: utf-8 -*-
import logging
import hashlib
import hmac
from datetime import date, datetime, time, timedelta
from numbers import Integral

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import sql
from odoo.tools.translate import _

from odoo.addons.time_off_responsible_approval import constants as approval_constants
from odoo.addons.time_off_work_handover import constants as handover_constants

_logger = logging.getLogger(__name__)

_EMERGENCY_LEAVE_CTX = "emergency_leave_confirmed"
_SKIP_EMERGENCY_LEAVE_CHECK_CTX = "skip_emergency_leave_check"
_SKIP_SUBMIT_BOT_NOTIFY_CTX = handover_constants.SKIP_SUBMIT_BOT_NOTIFY_CTX
_SKIP_OUTCOME_BOT_NOTIFY_CTX = approval_constants.SKIP_OUTCOME_BOT_NOTIFY_CTX
_SKIP_RESPONSIBLE_SUBMIT_NOTIFY_CTX = approval_constants.SKIP_RESPONSIBLE_SUBMIT_NOTIFY_CTX
_SHORT_LEAD_JOB_KEYS = frozenset({"nhân viên", "trưởng nhóm"})
_SHORT_LEAD_DAYS = 3
_DEFAULT_LEAD_DAYS = 7


class HolidaysRequest(models.Model):
    _inherit = "hr.leave"

''',
}


def bucket_method(name: str) -> str:
    if name in HANDOVER_METHODS:
        return "handover"
    if name in APPROVAL_METHODS:
        return "approval"
    if name in CORE_METHODS:
        return "core"
    raise KeyError(name)


def split_fields(fields_block: str):
    chunks = {"handover": [], "approval": [], "core": []}
    current = []
    depth = 0
    for line in fields_block.splitlines(keepends=True):
        if not line.strip():
            if current:
                current.append(line)
            continue
        if depth == 0 and line.strip().startswith("@api."):
            target = "core"
            chunks[target].append("".join(current))
            current = [line]
            depth = 0
            continue
        current.append(line)
        depth += line.count("(") - line.count(")")
        if depth <= 0 and line.strip() and not line.strip().endswith(","):
            if re.match(r"^\s+\w+\s*=", line):
                field_line = line
                if HANDOVER_FIELD_RE.match(field_line):
                    target = "handover"
                elif APPROVAL_FIELD_RE.match(field_line):
                    target = "approval"
                else:
                    target = "core"
                if len(current) > 1:
                    chunks[target].append("".join(current))
                    current = []
                    depth = 0
    if current:
        chunks["core"].append("".join(current))
    return chunks


def parse_blocks(text: str):
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines) and not lines[i].startswith("class HolidaysRequest"):
        i += 1
    i += 1
    fields_lines = []
    while i < len(lines):
        if lines[i].startswith("    def "):
            break
        fields_lines.append(lines[i])
        i += 1
    fields_block = "".join(fields_lines)
    methods = {}
    while i < len(lines):
        m = re.match(r"    def (\w+)\(", lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        start = i
        i += 1
        while i < len(lines) and not re.match(r"    def \w+\(", lines[i]):
            i += 1
        if name not in ("write", "create", "action_confirm"):
            methods[name] = "".join(lines[start:i])
    return fields_block, methods


WRITE_HANDOVER = '''
    def _handover_write_before(self, vals):
        if (
            vals.get("handover_employee_ids") is not None
            and not self.env.context.get("leave_fast_create")
            and not self.env.context.get("skip_handover_assignee_list_lock")
        ):
            viewer_emp = self.env.user.sudo().employee_id
            for leave in self:
                if leave.handover_escalated:
                    if not leave.handover_escalation_user_id or leave.handover_escalation_user_id != self.env.user:
                        raise UserError(
                            _(
                                "Sau khi quá hạn bàn giao công việc, chỉ người được chỉ định escalate "
                                "mới có thể thay đổi người nhận bàn giao."
                            )
                        )
                if viewer_emp and leave.employee_id and viewer_emp == leave.employee_id:
                    continue
                if leave._current_user_is_pending_handover_recipient():
                    raise UserError(
                        _(
                            "Bạn không thể tự thay đổi người bàn giao. "
                            "Vui lòng dùng nút Chấp nhận hoặc Từ chối bàn giao công việc."
                        )
                    )

    def _handover_write_after(self, vals, handover_lines_changed, submit_notify_target):
        if handover_lines_changed:
            self._sync_handover_employees_from_acceptance()
        if not self.env.context.get("leave_fast_create"):
            if vals.get("state") in ("confirm", "validate1"):
                self._mark_handover_requested_at()
            if vals.get("state") == "confirm" and submit_notify_target:
                submit_notify_target._notify_handover_recipients_submit_via_bot()
            if vals.get("state") in ("validate", "refuse", "cancel"):
                self._feedback_all_work_handover_activities()
            elif "handover_employee_ids" in vals:
                self.filtered(lambda l: l.state in _HANDOVER_ACTIVE_STATES)._sync_handover_acceptance_lines()
                self.filtered(lambda l: l.state in _HANDOVER_ACTIVE_STATES)._mark_pending_handover_lines_as_escalation_assigned()
                self.filtered(lambda l: l.state in _HANDOVER_ACTIVE_STATES)._schedule_work_handover_activities()

    def write(self, vals):
        handover_lines_changed = bool(
            vals.get("handover_acceptance_ids") is not None and not self.env.context.get("skip_handover_line_sync")
        )
        submit_notify_target = self.env["hr.leave"]
        if (
            vals.get("state") == "confirm"
            and not self.env.context.get("leave_fast_create")
            and not self.env.context.get(_SKIP_SUBMIT_BOT_NOTIFY_CTX)
        ):
            submit_notify_target = self.filtered(lambda l: l.state != "confirm" and l.handover_employee_ids)
        self._handover_write_before(vals)
        res = super().write(vals)
        self._handover_write_after(vals, handover_lines_changed, submit_notify_target)
        return res

    def action_confirm(self):
        missing_handover = self.filtered(
            lambda leave: not leave.skip_work_handover and not leave.handover_employee_ids
        )
        if missing_handover:
            raise UserError(
                _("Vui lòng chọn ít nhất một người nhận bàn giao công việc trước khi gửi đơn xin nghỉ phép.")
            )
        res = super().action_confirm()
        self._bootstrap_handover_workflow()
        self._mark_handover_requested_at()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._bootstrap_handover_workflow()
        records._mark_handover_requested_at()
        records.filtered(lambda l: l.state == "confirm")._notify_handover_recipients_submit_via_bot()
        return records
'''

WRITE_APPROVAL = '''
    def _approval_write_before(self, vals):
        ctx = {}
        if (
            vals.get("state") in ("validate", "refuse", "cancel")
            and not self.env.context.get("leave_fast_create")
            and not self.env.context.get(_SKIP_OUTCOME_BOT_NOTIFY_CTX)
        ):
            ctx["outcome_notify_prev_states"] = {leave.id: leave.state for leave in self}
        if (
            vals.get("state") == "confirm"
            and not self.env.context.get("leave_fast_create")
            and not self.env.context.get(_SKIP_RESPONSIBLE_SUBMIT_NOTIFY_CTX)
        ):
            ctx["responsible_submit_prev_states"] = {leave.id: leave.state for leave in self}
        reset_leaves = self.env["hr.leave"]
        if vals.get("state") == "confirm" and not self.env.context.get(_MULTI_STEP_RESET_CTX):
            reset_leaves = self.filtered(
                lambda l: l.validation_type == "multi_step_6" and l.state != "confirm"
            )
        ctx["reset_leaves"] = reset_leaves
        return ctx

    def _approval_write_after(self, vals, ctx):
        reset_leaves = ctx.get("reset_leaves") or self.env["hr.leave"]
        if reset_leaves:
            reset_leaves.mapped("multi_approval_line_ids").unlink()
            reset_leaves.with_context(**{_MULTI_STEP_RESET_CTX: True}).write({"multi_step_current": 1})
        self._ensure_responsible_approval_lines()
        to_timer = self.filtered(
            lambda l: l.validation_type == "employee_hr_responsibles"
            and l.state in ("confirm", "validate1")
            and (l.holiday_status_id.employee_responsible_approval_mode or "any") == "sequential"
            and l.responsible_approval_line_ids
        )
        if to_timer:
            to_timer._responsible_backfill_pending_since_if_missing()
        responsible_submit_prev_states = ctx.get("responsible_submit_prev_states") or {}
        if not self.env.context.get("leave_fast_create"):
            if vals.get("state") == "confirm" and responsible_submit_prev_states:
                submit_responsible_leaves = self.filtered(
                    lambda l: l.validation_type == "employee_hr_responsibles"
                    and l.state == "confirm"
                    and responsible_submit_prev_states.get(l.id) != "confirm"
                )
                if submit_responsible_leaves:
                    submit_responsible_leaves._ensure_responsible_approval_lines()
                    submit_responsible_leaves._responsible_backfill_pending_since_if_missing()
                    for leave in submit_responsible_leaves:
                        leave._notify_responsible_approvers_submission()
                        leave._notify_responsible_current_turn()
            outcome_notify_prev_states = ctx.get("outcome_notify_prev_states") or {}
            if outcome_notify_prev_states:
                for leave in self:
                    prev = outcome_notify_prev_states.get(leave.id)
                    if leave.state in ("validate", "refuse", "cancel") and leave.state != prev:
                        leave._notify_requester_approval_outcome_via_bot(
                            leave.state,
                            refusal_reason=self.env.context.get("refusal_reason"),
                            refuser_name=self.env.context.get("refuser_name"),
                        )

    def write(self, vals):
        ctx = self._approval_write_before(vals)
        res = super().write(vals)
        self._approval_write_after(vals, ctx)
        return res

    def action_confirm(self):
        res = super().action_confirm()
        subset = self.filtered(
            lambda l: l.validation_type == "employee_hr_responsibles" and l.state == "confirm"
        )
        if subset:
            subset._ensure_responsible_approval_lines()
            subset._responsible_backfill_pending_since_if_missing()
            for leave in subset:
                leave._notify_responsible_approvers_submission()
                leave._notify_responsible_current_turn()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_responsible_approval_lines()
        records._responsible_backfill_pending_since_if_missing()
        submit_responsible_leaves = records.filtered(
            lambda l: l.validation_type == "employee_hr_responsibles" and l.state == "confirm"
        )
        if submit_responsible_leaves:
            for leave in submit_responsible_leaves:
                leave._notify_responsible_approvers_submission()
                leave._notify_responsible_current_turn()
        return records
'''

WRITE_CORE = '''
    def write(self, vals):
        if vals and self._vals_trigger_emergency_leave_check(vals):
            if len(self) > 1:
                raise UserError(
                    _(
                        "Please edit and save one time off request at a time when changing dates, "
                        "employee, or time off type (advance-notice check)."
                    )
                )
            self._apply_emergency_leave_on_vals(vals, leave=self)
        return super().write(vals)

    def action_confirm(self):
        try:
            return super(
                HolidaysRequest,
                self.with_context(
                    **{
                        _SKIP_SUBMIT_BOT_NOTIFY_CTX: True,
                        _SKIP_RESPONSIBLE_SUBMIT_NOTIFY_CTX: True,
                    }
                ),
            ).action_confirm()
        except AttributeError:
            return True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._apply_emergency_leave_on_vals(vals)
        return super().create(vals_list)
'''


def split_fields_simple(fields_block: str):
    """Assign field blocks by scanning line-by-line field declarations."""
    chunks = {"handover": [], "approval": [], "core": []}
    buf = []
    decorators = []

    def flush():
        nonlocal buf, decorators
        if not buf and not decorators:
            return
        block = "".join(decorators) + "".join(buf)
        text = block
        target = "core"
        for line in buf:
            if HANDOVER_FIELD_RE.match(line):
                target = "handover"
                break
            if APPROVAL_FIELD_RE.match(line):
                target = "approval"
                break
        chunks[target].append(block)
        buf = []
        decorators = []

    for line in fields_block.splitlines(keepends=True):
        if line.strip().startswith("@api."):
            flush()
            decorators.append(line)
            continue
        if re.match(r"^\s{4}\w+\s*=", line) and buf:
            flush()
        buf.append(line)
    flush()
    return chunks


def main():
    text = SRC.read_text(encoding="utf-8")
    fields_block, methods = parse_blocks(text)
    field_chunks = split_fields_simple(fields_block)

    for bucket in ("handover", "approval", "core"):
        parts = [HEADERS[bucket]]
        parts.append("".join(field_chunks[bucket]))
        for name, body in sorted(methods.items(), key=lambda x: x[0]):
            if bucket_method(name) == bucket:
                parts.append(body)
        if bucket == "handover":
            parts.append(WRITE_HANDOVER)
        elif bucket == "approval":
            parts.append(WRITE_APPROVAL)
        elif bucket == "core":
            parts.append(WRITE_CORE)
        OUT[bucket].write_text("".join(parts), encoding="utf-8")
        print(f"Wrote {OUT[bucket]} ({len(''.join(parts).splitlines())} lines)")


if __name__ == "__main__":
    main()
