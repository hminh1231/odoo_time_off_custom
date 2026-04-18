from datetime import date, datetime, time, timedelta
from numbers import Integral

from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import sql
from odoo.tools.misc import format_date
from odoo.tools.translate import _

from odoo.addons.hr_job_title_vn.models.hr_version import JOB_TITLE_SELECTION

_MULTI_STEP_RESET_CTX = "time_off_multi_step_reset_skip"

# Order for sequential HR-responsible approval: by job title (keys from hr_job_title_vn), lowest first.
# Excludes the generic employee tier so approvers map to management chain only.
_HR_RESPONSIBLE_APPROVAL_JOB_TITLE_ORDER = tuple(
    key for key, _label in JOB_TITLE_SELECTION if key != "nhân viên"
)
# Key used in hr_job_title_vn hr.version job_title selection; only this tier may approve their own leave in HR Responsibles flow.
_DIRECTOR_JOB_TITLE_KEY = "giám đốc"
# Manual / sorted-by-title flows; org-chart mode allows one row per manager level (can exceed 6).
_MAX_EMPLOYEE_HR_RESPONSIBLES = 15
_HANDOVER_ACTIVITY_XMLID = "time_off_extra_approval.mail_act_leave_work_handover"
_TODO_ACTIVITY_XMLID = "mail.mail_activity_data_todo"

# Advance notice (calendar days between today and first leave day) by job title (hr_job_title_vn keys).
_EMERGENCY_LEAVE_CTX = "emergency_leave_confirmed"
_SKIP_EMERGENCY_LEAVE_CHECK_CTX = "skip_emergency_leave_check"
_SHORT_LEAD_JOB_KEYS = frozenset({"nhân viên", "trưởng nhóm"})
_SHORT_LEAD_DAYS = 3
_DEFAULT_LEAD_DAYS = 7


def _job_title_approval_sort_key(user, order_index):
    """Return (rank, user_id) for sorting approvers by job title."""
    title = user.employee_id.job_title if user.employee_id else False
    if title and title in order_index:
        return (order_index[title], user.id)
    # Unknown / empty title: after defined chain, stable by user id
    return (len(order_index) + 1, user.id)


class HolidaysRequest(models.Model):
    _inherit = "hr.leave"

    # Multi-step approval (demo). Used when hr.leave.type.leave_validation_type = 'multi_step_6'.
    multi_step_current = fields.Integer(
        string="Multi-step Current Step",
        default=1,
        help="Current step index (1..6) for multi-step time off approval (demo).",
    )
    multi_approval_line_ids = fields.One2many(
        comodel_name="hr.leave.multi.approval",
        inverse_name="leave_id",
        string="Multi-step Approval Log (Demo)",
        readonly=True,
    )

    can_multi_step_approve = fields.Boolean(
        string="Can Approve Current Multi-step (Demo)",
        compute="_compute_can_multi_step_approve",
    )

    extra_approver_user_ids = fields.Many2many(
        comodel_name="res.users",
        relation="hr_leave_extra_approver_user_rel",
        column1="leave_id",
        column2="user_id",
        string="Extra Time Off Approvers",
        compute="_compute_extra_approver_user_ids",
        store=True,
        readonly=True,
        help="Users who can approve/refuse this leave based on the leave type configuration.",
    )
    approval_actionable_user_ids = fields.Many2many(
        comodel_name="res.users",
        relation="hr_leave_approval_actionable_user_rel",
        column1="leave_id",
        column2="user_id",
        string="Can act on approval (technical)",
        compute="_compute_approval_actionable_user_ids",
        store=True,
        readonly=True,
        help="Users who can approve, validate, refuse, or use an extended approval action on this request.",
    )
    responsible_approval_line_ids = fields.One2many(
        comodel_name="hr.leave.responsible.approval",
        inverse_name="leave_id",
        string="Responsible Approval Log",
        readonly=True,
    )
    can_responsible_approve = fields.Boolean(
        string="Can Approve (Responsible Flow)",
        compute="_compute_can_responsible_approve",
    )
    handover_employee_ids = fields.Many2many(
        comodel_name="hr.employee",
        relation="hr_leave_handover_employee_rel",
        column1="leave_id",
        column2="employee_id",
        string="Work Handover To",
        help="Colleagues who receive work handover while this employee is on leave (max 5).",
    )
    unavailable_handover_employee_ids = fields.Many2many(
        comodel_name="hr.employee",
        compute="_compute_unavailable_handover_employee_ids",
        string="Unavailable handover recipients",
        help="Employees already on time off during this leave period.",
    )
    handover_acceptance_ids = fields.One2many(
        comodel_name="hr.leave.handover.acceptance",
        inverse_name="leave_id",
        string="Work Handover Responses",
        copy=False,
    )
    can_respond_handover = fields.Boolean(
        string="Can respond to work handover",
        compute="_compute_can_respond_handover",
    )
    handover_waiting_label = fields.Char(
        string="Handover status",
        compute="_compute_handover_waiting_label",
    )
    handover_refused_label = fields.Char(
        string="Handover refused status",
        compute="_compute_handover_refused_label",
    )
    handover_refusal_reason_label = fields.Text(
        string="Handover refusal reasons",
        compute="_compute_handover_refusal_reason_label",
    )
    can_manage_handover_replacement = fields.Boolean(
        string="Can manage handover replacement",
        compute="_compute_can_manage_handover_replacement",
    )
    approval_current_step_label = fields.Char(
        string="Current approval",
        compute="_compute_approval_current_step_label",
    )
    is_emergency_leave = fields.Boolean(
        string="Emergency leave (short notice)",
        default=False,
        copy=False,
        help="Set when the request is submitted with less advance notice than policy requires.",
    )
    emergency_leave_approver_notice = fields.Char(
        string="Emergency",
        compute="_compute_emergency_leave_approver_notice",
        store=True,
        help="Warning marker for approvers when this is emergency leave. "
        "Empty for employees who only have a work handover role on this request.",
    )

    def _register_hook(self):
        """Ensure DB columns exist on every registry load (not only on module -u)."""
        super()._register_hook()
        if self._name != "hr.leave":
            return
        cr = self.env.cr
        created_notice_column = False
        for column_name, column_type in (
            ("is_emergency_leave", "boolean"),
            ("emergency_leave_approver_notice", "varchar"),
        ):
            cr.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
                  AND table_schema = current_schema
                """,
                ("hr_leave", column_name),
            )
            if cr.fetchone():
                continue
            try:
                sql.create_column(cr, "hr_leave", column_name, column_type)
                if column_name == "emergency_leave_approver_notice":
                    created_notice_column = True
            except Exception:
                cr.execute(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = %s AND column_name = %s
                      AND table_schema = current_schema
                    """,
                    ("hr_leave", column_name),
                )
                if not cr.fetchone():
                    raise
        if created_notice_column:
            leaves = self.env["hr.leave"].sudo().search([])
            if leaves:
                leaves._compute_emergency_leave_approver_notice()

    # --- Advance notice vs job title (emergency leave) -----------------------------------------

    def _m2o_id(self, val):
        if val in (False, None):
            return False
        if isinstance(val, models.Model):
            return val.id
        if isinstance(val, (list, tuple)) and val:
            return val[0]
        return val

    def _parse_date_val(self, val):
        if val in (False, None):
            return False
        if isinstance(val, date) and not isinstance(val, datetime):
            return val
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, str):
            return fields.Date.from_string(val)
        return val

    def _required_lead_days_for_job_title(self, job_title):
        """Return minimum calendar days between today and leave start, or None if exempt."""
        if job_title == _DIRECTOR_JOB_TITLE_KEY:
            return None
        if job_title in _SHORT_LEAD_JOB_KEYS:
            return _SHORT_LEAD_DAYS
        return _DEFAULT_LEAD_DAYS

    def _merge_vals_for_emergency_check(self, vals, leave=None):
        """Merge write/create vals with existing leave for preview and enforcement."""
        merged = dict(vals or {})
        if leave:
            leave = leave[:1]
            for key in ("employee_id", "request_date_from", "request_date_to"):
                if key not in merged:
                    merged[key] = leave[key]
        return merged

    def _emergency_leave_violation_info(self, merged_vals, leave=None):
        """Return dict with keys: exempt, violation, required_days, delta_days, start_date."""
        if self.env.context.get(_SKIP_EMERGENCY_LEAVE_CHECK_CTX):
            return {"exempt": True, "violation": False}
        employee_id = self._m2o_id(merged_vals.get("employee_id"))
        if not employee_id and leave:
            employee_id = leave.employee_id.id
        employee = self.env["hr.employee"].sudo().browse(employee_id) if employee_id else self.env["hr.employee"]
        if not employee:
            return {"exempt": True, "violation": False}
        job_title = employee.job_title
        required = self._required_lead_days_for_job_title(job_title)
        if required is None:
            return {"exempt": True, "violation": False}
        start = self._parse_date_val(merged_vals.get("request_date_from"))
        if not start and leave:
            start = leave.request_date_from
        if not start:
            return {"exempt": True, "violation": False}
        today = fields.Date.context_today(self)
        delta = (start - today).days
        violation = delta < required
        return {
            "exempt": False,
            "violation": violation,
            "required_days": required,
            "delta_days": delta,
            "start_date": start,
        }

    def _apply_emergency_leave_on_vals(self, vals, leave=None):
        """Set is_emergency_leave on vals; raise UserError if violation without confirmation."""
        if self.env.context.get(_SKIP_EMERGENCY_LEAVE_CHECK_CTX) or self.env.context.get("leave_fast_create"):
            return
        merged = self._merge_vals_for_emergency_check(vals, leave=leave)
        info = self._emergency_leave_violation_info(merged, leave=leave)
        if info.get("exempt"):
            vals.setdefault("is_emergency_leave", False)
            return
        if not info.get("violation"):
            vals["is_emergency_leave"] = False
            return
        if self.env.context.get(_EMERGENCY_LEAVE_CTX):
            vals["is_emergency_leave"] = True
            return
        raise UserError(
            _(
                "This time off request does not meet the advance-notice rule. "
                "Confirm emergency leave in the application, or create the request with the "
                "“%(ctx)s” context key set to True.",
                ctx=_EMERGENCY_LEAVE_CTX,
            )
        )

    @api.model
    def check_emergency_leave_lead_time(self, res_id=False, vals=None):
        """Used by the UI before save. Returns needs_confirmation and translated dialog strings."""
        vals = vals or {}
        leave = self.env["hr.leave"]
        if res_id:
            leave = self.browse(res_id).exists()
            if leave:
                leave.check_access("read")
                leave.ensure_one()
        else:
            self.check_access("create")
        merged = self._merge_vals_for_emergency_check(vals, leave=leave if res_id and leave else None)
        info = self._emergency_leave_violation_info(merged, leave=leave if res_id and leave else None)
        if info.get("exempt") or not info.get("violation"):
            return {
                "needs_confirmation": False,
                "title": "",
                "message": "",
            }
        return {
            "needs_confirmation": True,
            "title": _("Emergency leave confirmation"),
            "message": _(
                "You are requesting emergency leave (less advance notice than required by policy). "
                "Are you sure you want to continue?"
            ),
        }

    @api.depends(
        "is_emergency_leave",
        "can_approve",
        "can_validate",
        "can_refuse",
        "can_responsible_approve",
        "can_multi_step_approve",
        "approval_actionable_user_ids",
    )
    def _compute_emergency_leave_approver_notice(self):
        """Show a marker only to people who can approve/refuse this request (not handover-only)."""
        user = self.env.user
        is_manager = user.has_group("hr_holidays.group_hr_holidays_manager")
        for leave in self:
            if not leave.is_emergency_leave:
                leave.emergency_leave_approver_notice = ""
                continue
            if is_manager:
                leave.emergency_leave_approver_notice = "\u26a0"
                continue
            if (
                leave.can_approve
                or leave.can_validate
                or leave.can_refuse
                or leave.can_responsible_approve
                or leave.can_multi_step_approve
                or user in leave.approval_actionable_user_ids
            ):
                leave.emergency_leave_approver_notice = "\u26a0"
            else:
                leave.emergency_leave_approver_notice = ""

    @api.constrains("handover_employee_ids")
    def _check_handover_employee_limit(self):
        for leave in self:
            if len(leave.handover_employee_ids) > 5:
                raise ValidationError(_("You can select at most 5 work handover recipients."))

    @api.constrains("state", "handover_employee_ids")
    def _check_handover_required_on_submit(self):
        for leave in self:
            if leave.state in ("confirm", "validate1", "validate") and not leave.handover_employee_ids:
                raise ValidationError(
                    _("Please select at least one work handover recipient before submitting the time off request.")
                )

    def _get_requested_interval(self):
        """Return (start_dt, end_dt) of the current leave request."""
        self.ensure_one()
        start_dt = self.date_from
        end_dt = self.date_to

        if not start_dt and self.request_date_from:
            start_dt = datetime.combine(self.request_date_from, time.min)

        if not end_dt:
            end_date = self.request_date_to or self.request_date_from
            if end_date:
                # Inclusive day range -> convert to half-open [start, end) interval.
                end_dt = datetime.combine(end_date + timedelta(days=1), time.min)

        if start_dt and end_dt and end_dt <= start_dt:
            end_dt = start_dt + timedelta(minutes=1)
        return start_dt, end_dt

    def _get_unavailable_handover_employees(self):
        """Employees in handover list that already have overlapping time off."""
        self.ensure_one()
        if not self.handover_employee_ids:
            return self.env["hr.employee"]
        start_dt, end_dt = self._get_requested_interval()
        if not start_dt or not end_dt:
            return self.env["hr.employee"]
        overlapping = self.env["hr.leave"].sudo().search(
            [
                ("id", "!=", self.id or 0),
                ("employee_id", "in", self.handover_employee_ids.ids),
                ("state", "in", ("confirm", "validate1", "validate")),
                ("date_from", "<", end_dt),
                ("date_to", ">", start_dt),
            ]
        )
        return overlapping.mapped("employee_id")

    @api.depends(
        "request_date_from",
        "request_date_to",
        "date_from",
        "date_to",
        "employee_id",
        "employee_id.parent_id",
    )
    def _compute_unavailable_handover_employee_ids(self):
        Employee = self.env["hr.employee"]
        for leave in self:
            start_dt, end_dt = leave._get_requested_interval()
            if not start_dt or not end_dt:
                leave.unavailable_handover_employee_ids = Employee
                continue
            overlapping = self.env["hr.leave"].sudo().search(
                [
                    ("id", "!=", leave.id or 0),
                    ("state", "in", ("confirm", "validate1", "validate")),
                    ("date_from", "<", end_dt),
                    ("date_to", ">", start_dt),
                ]
            )
            leave.unavailable_handover_employee_ids = overlapping.mapped("employee_id")

    @api.constrains(
        "handover_employee_ids",
        "request_date_from",
        "request_date_to",
        "date_from",
        "date_to",
        "state",
    )
    def _check_handover_employee_availability(self):
        for leave in self.filtered("handover_employee_ids"):
            unavailable = leave._get_unavailable_handover_employees()
            if unavailable:
                raise ValidationError(
                    _(
                        "Selected work handover recipient(s) already have time off in this period: %(names)s. "
                        "Please choose other colleagues."
                    )
                    % {"names": ", ".join(unavailable.mapped("name"))}
                )

    @api.onchange(
        "handover_employee_ids",
        "request_date_from",
        "request_date_to",
        "request_hour_from",
        "request_hour_to",
        "request_date_from_period",
        "request_date_to_period",
    )
    def _onchange_handover_employee_availability(self):
        for leave in self.filtered("handover_employee_ids"):
            unavailable = leave._get_unavailable_handover_employees()
            if unavailable:
                allowed = leave.handover_employee_ids - unavailable
                leave.update({"handover_employee_ids": [Command.set(allowed.ids)]})
                return {
                    "domain": {
                        "handover_employee_ids": [
                            ("id", "not in", unavailable.ids),
                            ("id", "!=", leave.employee_id.id),
                            ("user_id", "!=", False),
                        ]
                    },
                    "warning": {
                        "title": _("Validation Warning"),
                        "message": _(
                            "Cannot assign work handover to %(names)s because they already have time off in this period. "
                            "Those recipients were removed. Please select someone else."
                        )
                        % {"names": ", ".join(unavailable.mapped("name"))},
                    }
                }

    @api.depends(
        "state",
        "handover_acceptance_ids.state",
        "handover_acceptance_ids.employee_id",
        "handover_employee_ids",
    )
    def _compute_can_respond_handover(self):
        for leave in self:
            leave.can_respond_handover = False
            if leave.state != "confirm":
                continue
            emp = leave.env.user.employee_id
            if not emp or emp not in leave.handover_employee_ids:
                continue
            line = leave.handover_acceptance_ids.filtered(lambda l: l.employee_id == emp)[:1]
            leave.can_respond_handover = bool(line and line.state == "pending")

    @api.depends(
        "state",
        "handover_employee_ids",
        "handover_employee_ids.name",
        "handover_acceptance_ids.state",
        "handover_acceptance_ids.employee_id",
        "handover_acceptance_ids.employee_id.name",
    )
    def _compute_handover_waiting_label(self):
        for leave in self:
            leave.handover_waiting_label = False
            if leave.state not in ("confirm", "validate1") or not leave.handover_employee_ids:
                continue
            waiting = leave._get_handover_blocking_employees()
            if waiting:
                leave.handover_waiting_label = _("Waiting handover: %s") % ", ".join(waiting.mapped("name"))
            else:
                leave.handover_waiting_label = _("All handover recipients accepted")

    @api.depends(
        "state",
        "handover_acceptance_ids.state",
        "handover_acceptance_ids.employee_id",
        "handover_acceptance_ids.employee_id.name",
    )
    def _compute_handover_refused_label(self):
        for leave in self:
            leave.handover_refused_label = False
            if leave.state not in ("confirm", "validate1"):
                continue
            refused = leave.handover_acceptance_ids.filtered(lambda l: l.state == "refused").mapped("employee_id")
            if refused:
                leave.handover_refused_label = _("Refused handover: %s") % ", ".join(refused.mapped("name"))

    @api.depends(
        "state",
        "handover_acceptance_ids.state",
        "handover_acceptance_ids.employee_id",
        "handover_acceptance_ids.employee_id.name",
        "handover_acceptance_ids.refusal_reason",
    )
    def _compute_handover_refusal_reason_label(self):
        for leave in self:
            leave.handover_refusal_reason_label = False
            if leave.state not in ("confirm", "validate1"):
                continue
            refused_lines = leave.handover_acceptance_ids.filtered(lambda line: line.state == "refused")
            items = []
            for line in refused_lines:
                if line.refusal_reason:
                    items.append(_("%(name)s: %(reason)s") % {"name": line.employee_id.name, "reason": line.refusal_reason})
            leave.handover_refusal_reason_label = "\n".join(items) if items else False

    @api.depends("state", "employee_id", "employee_id.user_id", "handover_refused_label")
    def _compute_can_manage_handover_replacement(self):
        for leave in self:
            leave.can_manage_handover_replacement = bool(
                leave.state in ("confirm", "validate1")
                and leave.handover_refused_label
                and leave.employee_id
                and leave.employee_id.user_id == leave.env.user
            )

    @api.depends(
        "holiday_status_id",
        "holiday_status_id.extra_responsible_user_ids",
        "holiday_status_id.extra_responsible_department_ids",
        "validation_type",
        "multi_step_current",
        "employee_id",
        "employee_id.hr_responsible_ids",
        "employee_id.hr_responsible_id",
        "holiday_status_id.multi_approval_step_ids",
        "holiday_status_id.multi_approval_step_ids.approver_user_id",
        "holiday_status_id.multi_approval_step_ids.approver_user_ids",
        "holiday_status_id.multi_approval_step_ids.approver_department_ids",
        "holiday_status_id.employee_responsible_source",
        "employee_id.parent_id",
        "employee_id.parent_id.parent_id",
        "employee_id.parent_id.parent_id.parent_id",
        "employee_id.parent_id.parent_id.parent_id.parent_id",
        "employee_id.parent_id.parent_id.parent_id.parent_id.parent_id",
    )
    def _compute_extra_approver_user_ids(self):
        for leave in self:
            if leave.validation_type == "multi_step_6":
                step = leave._get_current_multi_step()
                leave.extra_approver_user_ids = step and step._get_all_approver_users() or self.env["res.users"]
                continue

            if leave.validation_type == "employee_hr_responsibles":
                leave.extra_approver_user_ids = leave._get_responsible_approval_users()
                continue

            users = leave.holiday_status_id.extra_responsible_user_ids
            if leave.holiday_status_id.extra_responsible_department_ids:
                dept_users = leave.holiday_status_id.extra_responsible_department_ids.mapped("member_ids.user_id")
                dept_users = dept_users.filtered(lambda u: u and not u.share)
                users |= dept_users
            leave.extra_approver_user_ids = users

    @api.depends(
        "state",
        "employee_id",
        "employee_id.job_title",
        "employee_id.leave_manager_id",
        "holiday_status_id",
        "holiday_status_id.responsible_ids",
        "extra_approver_user_ids",
        "multi_step_current",
        "responsible_approval_line_ids",
        "responsible_approval_line_ids.state",
        "responsible_approval_line_ids.user_id",
    )
    def _compute_approval_actionable_user_ids(self):
        """Users for whom at least one approval action would be allowed (matches Kanban/form buttons)."""
        Users = self.env["res.users"]
        group_user = self.env.ref("hr_holidays.group_hr_holidays_user")
        group_manager = self.env.ref("hr_holidays.group_hr_holidays_manager")
        # Odoo 19: res.users uses group_ids / all_group_ids — not groups_id (invalid domain field).
        base_hr = Users.sudo().search(
            [
                "&",
                ("share", "=", False),
                "|",
                ("all_group_ids", "in", [group_user.id]),
                ("all_group_ids", "in", [group_manager.id]),
            ]
        )
        manager_users = base_hr.filtered(lambda u: group_manager in u.all_group_ids)

        for leave in self:
            if not leave.id or leave.state not in ("confirm", "validate1"):
                leave.approval_actionable_user_ids = Users
                continue

            # Custom flows: compute from current workflow state directly.
            if leave.validation_type == "employee_hr_responsibles":
                pending = leave.responsible_approval_line_ids.filtered(
                    lambda l: l.state == "pending" and l.user_id and not l.user_id.share
                ).sorted("sequence")
                if not pending:
                    leave.approval_actionable_user_ids = Users
                    continue
                mode = leave.holiday_status_id.employee_responsible_approval_mode or "any"
                if mode == "sequential":
                    leave.approval_actionable_user_ids = pending[:1].mapped("user_id")
                else:
                    leave.approval_actionable_user_ids = pending.mapped("user_id")
                continue

            if leave.validation_type == "multi_step_6":
                actionable = leave._get_multi_step_approvers().filtered(lambda u: u and not u.share)
                leave.approval_actionable_user_ids = actionable | manager_users
                continue

            candidates = base_hr | leave.extra_approver_user_ids
            if leave.employee_id.leave_manager_id:
                candidates |= leave.employee_id.leave_manager_id
            if leave.holiday_status_id.responsible_ids:
                candidates |= leave.holiday_status_id.responsible_ids
            if leave.validation_type == "multi_step_6":
                candidates |= leave._get_multi_step_approvers()

            candidates = candidates.filtered(lambda u: u and not u.share)
            actionable = Users
            for user in candidates:
                lu = leave.with_user(user)
                if (
                    lu.can_approve
                    or lu.can_validate
                    or lu.can_refuse
                    or lu.can_multi_step_approve
                    or lu.can_responsible_approve
                ):
                    actionable |= user
            leave.approval_actionable_user_ids = actionable

    def _get_current_multi_step(self):
        """Return the currently active multi-step config for this leave."""
        self.ensure_one()
        if self.validation_type != "multi_step_6":
            return self.env["hr.leave.type.approval.step"]
        steps = self.holiday_status_id.multi_approval_step_ids
        return steps.filtered(lambda s: s.sequence == self.multi_step_current)[:1]

    def activity_update(self):
        """Make pending approval activities visible immediately in Today/Late filters."""
        res = super().activity_update()
        today = fields.Date.today()
        for leave in self.filtered(lambda l: l.state in ("confirm", "validate1")):
            xmlids = (
                ["hr_holidays.mail_act_leave_approval"]
                if leave.state == "confirm"
                else ["hr_holidays.mail_act_leave_second_approval"]
            )
            activities = leave.activity_search(xmlids, only_automated=True).filtered(
                lambda a: a.date_deadline and a.date_deadline > today
            )
            if activities:
                activities.write({"date_deadline": today})
        return res

    def _get_employee_responsible_users(self):
        self.ensure_one()
        users = self.employee_id.hr_responsible_ids
        if not users and self.employee_id.hr_responsible_id:
            users = self.employee_id.hr_responsible_id
        return users

    def _get_org_chart_approver_users_ordered(self):
        """Walk reporting line (parent_id) from direct manager upward: one approver per org level.

        The previous implementation matched at most one person per *job title tier* along the chain, so
        two managers with the same title (or a middle manager without a distinct tier) were skipped.
        This matches the org chart: Tester 3 → Tester 2 → … up to the top, each with a linked user.
        """
        self.ensure_one()
        employee = self.employee_id
        if not employee:
            return self.env["res.users"]
        user_ids = []
        seen = set()
        Users = self.env["res.users"]
        cur = employee.parent_id
        while cur:
            mgr = cur.sudo()
            if mgr.user_id and not mgr.user_id.share:
                uid = mgr.user_id.id
                if uid not in seen:
                    user_ids.append(uid)
                    seen.add(uid)
            cur = mgr.parent_id
        return Users.browse(user_ids)

    def _get_responsible_approval_users(self):
        self.ensure_one()
        if self.holiday_status_id.employee_responsible_source == "org_chart":
            users = self._get_org_chart_approver_users_ordered()
            # Direct manager must be able to approve first: org-chart tiers can omit them if title read failed.
            parent = self.employee_id.parent_id.sudo() if self.employee_id else self.env["hr.employee"]
            if parent and parent.user_id and not parent.user_id.share:
                pu = parent.user_id
                if pu.id not in users.ids:
                    users = pu | users
                elif users.ids and users.ids[0] != pu.id:
                    users = self.env["res.users"].browse([pu.id] + [uid for uid in users.ids if uid != pu.id])
            return users
        return self._get_employee_responsible_users()

    def _sort_responsible_users_by_job_title(self, users):
        """Sequential chain order: trưởng nhóm → trưởng BP → kiểm soát → trưởng phòng HCNS → giám đốc (see hr_job_title_vn)."""
        self.ensure_one()
        order_index = {title: idx for idx, title in enumerate(_HR_RESPONSIBLE_APPROVAL_JOB_TITLE_ORDER)}
        return users.sorted(
            key=lambda u: _job_title_approval_sort_key(u, order_index)
        )

    def _employee_hr_blocks_self_approval_non_director(self, user=None):
        """In Employee HR Responsibles, only Giám đốc may approve/refuse their own request (others must not act on own leave)."""
        self.ensure_one()
        if self.validation_type != "employee_hr_responsibles":
            return False
        user = user or self.env.user
        emp = self.employee_id
        if not emp or not emp.user_id or emp.user_id != user:
            return False
        return (emp.job_title or "") != _DIRECTOR_JOB_TITLE_KEY

    def _get_multi_step_approvers(self):
        self.ensure_one()
        step = self._get_current_multi_step()
        return step and step._get_all_approver_users() or self.env["res.users"]

    def _multi_step_previous_steps_logged(self):
        """Steps 1..(current-1) must each appear in the approval log (sequential chain)."""
        self.ensure_one()
        if self.multi_step_current <= 1:
            return True
        done_seqs = set(self.multi_approval_line_ids.mapped("step_id.sequence"))
        needed = set(range(1, self.multi_step_current))
        return needed.issubset(done_seqs)

    def _bootstrap_handover_workflow(self):
        """Create handover acknowledgement rows and schedule activities (clock menu) for recipients."""
        if self.env.context.get("leave_fast_create") or self.env.context.get("mail_activity_automation_skip"):
            return self
        leaves = self.filtered(lambda l: l.state == "confirm" and l.handover_employee_ids)
        leaves._sync_handover_acceptance_lines()
        leaves._schedule_work_handover_activities()
        return self

    def _sync_handover_acceptance_lines(self):
        Acceptance = self.env["hr.leave.handover.acceptance"].sudo()
        for leave in self.filtered(lambda l: l.state == "confirm"):
            current = leave.handover_employee_ids
            existing = leave.handover_acceptance_ids.sudo()
            to_remove = existing.filtered(lambda l: l.employee_id not in current)
            for line in to_remove:
                user = line.employee_id.user_id
                if user:
                    leave.activity_unlink(
                        [_HANDOVER_ACTIVITY_XMLID],
                        user_id=user.id,
                        only_automated=False,
                    )
            to_remove.unlink()
            existing = leave.handover_acceptance_ids.sudo()
            for emp in current:
                if not existing.filtered(lambda l: l.employee_id == emp):
                    Acceptance.create(
                        {
                            "leave_id": leave.id,
                            "employee_id": emp.id,
                        }
                    )
        return self

    def _schedule_work_handover_activities(self):
        today = fields.Date.today()
        for leave in self.filtered(lambda l: l.state == "confirm" and l.handover_employee_ids):
            requester = leave.employee_id
            requester_name = requester.name if requester else leave.display_name
            leave_type = leave.holiday_status_id.name if leave.holiday_status_id else ""
            date_from = leave.request_date_from
            if not date_from and leave.date_from:
                date_from = leave.date_from.date()
            date_txt = format_date(self.env, date_from) if date_from else ""
            for line in leave.handover_acceptance_ids.sudo().filtered(lambda l: l.state == "pending"):
                user = line.employee_id.user_id
                if not user or user.share:
                    continue
                open_act = leave.activity_search(
                    [_HANDOVER_ACTIVITY_XMLID],
                    user_id=user.id,
                    only_automated=False,
                )
                if open_act:
                    continue
                note = Markup("<p>%s</p><p>%s</p>") % (
                    _(
                        "You were asked to cover work while %(name)s is away (%(leave_type)s, %(dates)s)."
                    )
                    % {"name": requester_name, "leave_type": leave_type, "dates": date_txt},
                    _("Open this request and choose Accept work handover or Refuse work handover."),
                )
                leave.activity_schedule(
                    _HANDOVER_ACTIVITY_XMLID,
                    date_deadline=today,
                    user_id=user.id,
                    note=note,
                )
        return self

    def _feedback_all_work_handover_activities(self):
        for leave in self:
            leave.activity_feedback(
                [_HANDOVER_ACTIVITY_XMLID],
                only_automated=False,
                feedback=_("Time off request closed."),
            )
        return self

    def _notify_requester_handover_refusal(self, refused_employee, reason=None):
        self.ensure_one()
        requester = self.employee_id
        if not requester or not requester.user_id or requester.user_id.share:
            return
        reason = (reason or "").strip()
        reason_suffix = _("\nReason: %s") % reason if reason else ""
        body = _(
            "%(recipient)s declined your work handover request for %(leave)s. "
            "Do you want to select another colleague?"
        ) % {
            "recipient": refused_employee.name or refused_employee.display_name,
            "leave": self.display_name,
        } + reason_suffix
        if requester.user_id.partner_id:
            self.message_notify(
                partner_ids=requester.user_id.partner_id.ids,
                subject=_("Work handover declined"),
                body=body,
            )
        existing_todo = self.activity_search(
            [_TODO_ACTIVITY_XMLID],
            user_id=requester.user_id.id,
            additional_domain=[("summary", "=", _("Update work handover recipients"))],
            only_automated=False,
        )
        if not existing_todo:
            self.activity_schedule(
                _TODO_ACTIVITY_XMLID,
                user_id=requester.user_id.id,
                summary=_("Update work handover recipients"),
                note=Markup("<p>%s</p><p>%s</p>") % (
                    body,
                    _(
                        "Open this request, then either remove the refused recipient "
                        "or select another colleague in Work Handover To."
                    ),
                ),
            )

    def _get_handover_blocking_employees(self):
        """Employees who have not accepted handover yet for current approval stage."""
        self.ensure_one()
        if self.state not in ("confirm", "validate1") or not self.handover_employee_ids:
            return self.env["hr.employee"]
        active_recipients = self.handover_employee_ids
        accepted = self.handover_acceptance_ids.filtered(
            lambda l: l.employee_id in active_recipients and l.state == "accepted"
        ).mapped("employee_id")
        return active_recipients - accepted

    def _handover_ready_for_approval(self):
        self.ensure_one()
        return not self._get_handover_blocking_employees()

    def _ensure_handover_ready_for_approval(self, raise_if_not_ready=True):
        blocked = self.env["hr.leave"]
        for leave in self:
            if leave._get_handover_blocking_employees():
                blocked |= leave
        if not blocked:
            return True
        if not raise_if_not_ready:
            return False
        leave = blocked[:1]
        names = ", ".join(leave._get_handover_blocking_employees().mapped("name"))
        raise UserError(
            _(
                "Approval is locked until all work handover recipients accept. "
                "Still waiting for: %(names)s."
            )
            % {"names": names}
        )

    def action_handover_accept(self):
        self.ensure_one()
        emp = self.env.user.sudo().employee_id
        if not emp or emp not in self.handover_employee_ids:
            raise UserError(_("Only selected work handover recipients can respond here."))
        line = self.handover_acceptance_ids.sudo().filtered(lambda l: l.employee_id == emp)[:1]
        if not line or line.state != "pending":
            raise UserError(_("You have already responded to this work handover request."))
        line.write(
            {
                "state": "accepted",
                "responded_at": fields.Datetime.now(),
                "refusal_reason": False,
            }
        )
        self.activity_feedback(
            [_HANDOVER_ACTIVITY_XMLID],
            user_id=self.env.user.id,
            only_automated=False,
            feedback=_("Accepted work handover."),
        )
        self.message_post(
            body=_("%s accepted the work handover.") % self.env.user.display_name,
            subtype_xmlid="mail.mt_note",
        )
        return True

    def action_handover_refuse(self):
        self.ensure_one()
        emp = self.env.user.sudo().employee_id
        if not emp or emp not in self.handover_employee_ids:
            raise UserError(_("Only selected work handover recipients can respond here."))
        line = self.handover_acceptance_ids.sudo().filtered(lambda l: l.employee_id == emp)[:1]
        if not line or line.state != "pending":
            raise UserError(_("You have already responded to this work handover request."))
        return {
            "name": _("Refuse Work Handover"),
            "type": "ir.actions.act_window",
            "target": "new",
            "res_model": "hr.leave.handover.refuse.wizard",
            "view_mode": "form",
            "views": [[False, "form"]],
            "context": {
                "default_leave_id": self.id,
                "dialog_size": "medium",
            },
        }

    def action_handover_refuse_with_reason(self, reason):
        self.ensure_one()
        reason = (reason or "").strip()
        emp = self.env.user.sudo().employee_id
        if not emp or emp not in self.handover_employee_ids:
            raise UserError(_("Only selected work handover recipients can respond here."))
        line = self.handover_acceptance_ids.sudo().filtered(lambda l: l.employee_id == emp)[:1]
        if not line or line.state != "pending":
            raise UserError(_("You have already responded to this work handover request."))
        line.write(
            {
                "state": "refused",
                "responded_at": fields.Datetime.now(),
                "refusal_reason": reason,
            }
        )
        self.activity_feedback(
            [_HANDOVER_ACTIVITY_XMLID],
            user_id=self.env.user.id,
            only_automated=False,
            feedback=_("Refused work handover."),
        )
        reason_html = (
            Markup("<br/><strong>%s</strong> %s")
            % (_("Reason:"), reason)
            if reason
            else Markup("")
        )
        self.message_post(
            body=Markup("%s%s")
            % (_("%s refused the work handover.") % self.env.user.display_name, reason_html),
            subtype_xmlid="mail.mt_note",
        )
        self._notify_requester_handover_refusal(emp, reason=reason)
        return True

    def _vals_trigger_emergency_leave_check(self, vals):
        if not vals:
            return False
        return bool(
            {"employee_id", "request_date_from", "request_date_to", "holiday_status_id"}.intersection(vals)
        )

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
        reset_leaves = self.env["hr.leave"]
        if vals.get("state") == "confirm" and not self.env.context.get(_MULTI_STEP_RESET_CTX):
            reset_leaves = self.filtered(
                lambda l: l.validation_type == "multi_step_6" and l.state != "confirm"
            )
        res = super().write(vals)
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
        if not self.env.context.get("leave_fast_create"):
            if vals.get("state") in ("validate", "refuse", "cancel"):
                self._feedback_all_work_handover_activities()
            elif "handover_employee_ids" in vals:
                self.filtered(lambda l: l.state == "confirm")._sync_handover_acceptance_lines()
                self.filtered(lambda l: l.state == "confirm")._schedule_work_handover_activities()
        return res

    @api.depends(
        "validation_type",
        "state",
        "multi_step_current",
        "holiday_status_id",
        "handover_employee_ids",
        "handover_acceptance_ids.state",
        "handover_acceptance_ids.employee_id",
    )
    def _compute_can_multi_step_approve(self):
        for leave in self:
            can = False
            if leave.validation_type == "multi_step_6" and leave.state == "confirm":
                is_manager = leave.env.user.has_group("hr_holidays.group_hr_holidays_manager")
                if is_manager:
                    can = True
                else:
                    can = leave.env.user in leave._get_multi_step_approvers()
            if can and not leave._handover_ready_for_approval():
                can = False
            leave.can_multi_step_approve = can

    @api.depends(
        "state",
        "employee_id",
        "department_id",
        "holiday_status_id",
        "handover_employee_ids",
        "handover_acceptance_ids.state",
        "handover_acceptance_ids.employee_id",
    )
    def _compute_can_approve(self):
        super()._compute_can_approve()
        for leave in self.filtered(
            lambda h: h.validation_type in ("employee_hr_responsibles", "multi_step_6")
        ):
            leave.can_approve = False
        for leave in self:
            if leave.can_approve and not leave._handover_ready_for_approval():
                leave.can_approve = False

    @api.depends(
        "state",
        "employee_id",
        "department_id",
        "holiday_status_id",
        "handover_employee_ids",
        "handover_acceptance_ids.state",
        "handover_acceptance_ids.employee_id",
    )
    def _compute_can_validate(self):
        super()._compute_can_validate()
        for leave in self.filtered(
            lambda h: h.validation_type in ("employee_hr_responsibles", "multi_step_6")
        ):
            leave.can_validate = False
        for leave in self:
            if leave.can_validate and not leave._handover_ready_for_approval():
                leave.can_validate = False

    @api.depends(
        "state",
        "employee_id",
        "department_id",
        "holiday_status_id",
        "handover_employee_ids",
        "handover_acceptance_ids.state",
        "handover_acceptance_ids.employee_id",
    )
    def _compute_can_refuse(self):
        super()._compute_can_refuse()
        for leave in self.filtered(
            lambda h: h.validation_type in ("employee_hr_responsibles", "multi_step_6")
        ):
            leave.can_refuse = False
        for leave in self:
            if leave.can_refuse and not leave._handover_ready_for_approval():
                leave.can_refuse = False

    def _is_extra_approver(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        return user in self.extra_approver_user_ids

    def _get_responsible_for_approval(self):
        if self.validation_type == "employee_hr_responsibles":
            return self._get_responsible_approval_users()
        if self.validation_type == "multi_step_6":
            return self._get_multi_step_approvers()

        res = super()._get_responsible_for_approval()
        # Only HR-step validations use responsible_ids; for manager validations this is handled by employee leave manager.
        if self.employee_id and (
            self.validation_type == "hr" or (self.validation_type == "both" and self.state == "validate1")
        ):
            res |= self.extra_approver_user_ids
        return res

    @api.depends(
        "validation_type",
        "state",
        "holiday_status_id",
        "holiday_status_id.leave_validation_type",
        "holiday_status_id.employee_responsible_approval_mode",
        "holiday_status_id.employee_responsible_source",
        "employee_id",
        "employee_id.job_title",
        "employee_id.hr_responsible_ids",
        "employee_id.hr_responsible_id",
        "responsible_approval_line_ids",
        "responsible_approval_line_ids.state",
        "responsible_approval_line_ids.user_id",
        "handover_employee_ids",
        "handover_acceptance_ids.state",
        "handover_acceptance_ids.employee_id",
    )
    def _compute_can_responsible_approve(self):
        for leave in self:
            can = False
            # validate1: can appear on mixed/old data; still allow Responsible actions if approval lines exist.
            if leave.validation_type == "employee_hr_responsibles" and leave.state in ("confirm", "validate1"):
                if leave.state == "validate1" and not leave.responsible_approval_line_ids:
                    can = False
                else:
                    mode = leave.holiday_status_id.employee_responsible_approval_mode
                    approvers = leave._get_responsible_approval_users()
                    is_manager = leave.env.user.has_group("hr_holidays.group_hr_holidays_manager")
                    # Sequential: every user (including Time Off Administrators) must wait for the current
                    # pending line so "Waiting For Me" / Kanban buttons match chain order — not all admins at once.
                    if mode == "sequential":
                        if leave._employee_hr_blocks_self_approval_non_director(leave.env.user):
                            can = False
                        elif (
                            not leave.responsible_approval_line_ids
                            and approvers
                            and leave.state == "confirm"
                        ):
                            can = leave.env.user == approvers[0]
                        else:
                            user_line = leave.responsible_approval_line_ids.filtered(
                                lambda l: l.user_id == leave.env.user and l.state == "pending"
                            )[:1]
                            first_pending = leave.responsible_approval_line_ids.filtered(
                                lambda l: l.state == "pending"
                            ).sorted("sequence")[:1]
                            can = bool(user_line and first_pending and user_line == first_pending)
                    elif is_manager:
                        can = True
                    elif leave.env.user in approvers:
                        if leave._employee_hr_blocks_self_approval_non_director(leave.env.user):
                            can = False
                        else:
                            can = bool(
                                leave.responsible_approval_line_ids.filtered(
                                    lambda l: l.user_id == leave.env.user and l.state == "pending"
                                )[:1]
                            )
            if can and not leave._handover_ready_for_approval():
                can = False
            leave.can_responsible_approve = can

    @api.depends(
        "validation_type",
        "state",
        "multi_step_current",
        "holiday_status_id.employee_responsible_approval_mode",
        "holiday_status_id.multi_approval_step_ids",
        "responsible_approval_line_ids",
        "responsible_approval_line_ids.state",
        "responsible_approval_line_ids.sequence",
        "responsible_approval_line_ids.user_id",
    )
    def _compute_approval_current_step_label(self):
        """One-line hint for Kanban/list: who should act next (HR Responsibles / multi-step)."""
        for leave in self:
            leave.approval_current_step_label = False
            if leave.state not in ("confirm", "validate1"):
                continue
            vt = leave.validation_type
            if vt == "employee_hr_responsibles":
                pending = leave.responsible_approval_line_ids.filtered(
                    lambda line: line.state == "pending"
                ).sorted("sequence")
                if not pending:
                    continue
                mode = leave.holiday_status_id.employee_responsible_approval_mode or "any"
                total = len(leave.responsible_approval_line_ids)
                if mode == "sequential":
                    cur = pending[:1]
                    name = cur.user_id.name or ""
                    leave.approval_current_step_label = _("Step %(step)d / %(total)d · %(name)s") % {
                        "step": cur.sequence,
                        "total": total,
                        "name": name,
                    }
                else:
                    leave.approval_current_step_label = ", ".join(
                        n for n in pending.mapped("user_id.name") if n
                    ) or False
            elif vt == "multi_step_6":
                step = leave._get_current_multi_step()
                if not step:
                    continue
                users = step._get_all_approver_users()
                names = ", ".join(n for n in users.mapped("name") if n)
                if step.name and names:
                    leave.approval_current_step_label = _("%(step)s · %(names)s") % {
                        "step": step.name,
                        "names": names,
                    }
                elif names:
                    leave.approval_current_step_label = names
                elif step.name:
                    leave.approval_current_step_label = step.name

    def _init_responsible_approval_lines(self):
        line_model = self.env["hr.leave.responsible.approval"].sudo()
        for leave in self:
            if leave.validation_type != "employee_hr_responsibles" or not leave.employee_id:
                continue
            if leave.responsible_approval_line_ids:
                continue
            lt = leave.holiday_status_id
            approvers = leave._get_responsible_approval_users()
            if lt.employee_responsible_approval_mode == "sequential" and lt.employee_responsible_source != "org_chart":
                approvers = leave._sort_responsible_users_by_job_title(approvers)
            if not approvers:
                if lt.employee_responsible_source == "org_chart":
                    raise UserError(
                        _(
                            "No approver was found from the organization chart. Set managers on the employee "
                            "and job titles (team lead → dept head → controller → HR head → director) on the hierarchy."
                        )
                    )
                raise UserError(_("This employee has no HR Responsible configured."))
            if len(approvers) > _MAX_EMPLOYEE_HR_RESPONSIBLES:
                raise UserError(
                    _("This workflow supports up to %(max)s HR Responsibles per employee.")
                    % {"max": _MAX_EMPLOYEE_HR_RESPONSIBLES}
                )
            now = fields.Datetime.now()
            for sequence, user in enumerate(approvers, start=1):
                vals = {
                    "leave_id": leave.id,
                    "user_id": user.id,
                    "sequence": sequence,
                }
                if sequence == 1 and lt.employee_responsible_approval_mode == "sequential":
                    vals["pending_since"] = now
                line_model.create(vals)

    def _ensure_responsible_approval_lines(self):
        """Create approval log rows when a request is already To Approve but lines were never created.

        Lines are normally added in ``action_confirm``; some code paths set ``state`` to confirm via
        ``write``/import/wizards without going through that method, which left no pending step and no
        Step label until someone saved again.
        """
        to_init = self.filtered(
            lambda l: l.validation_type == "employee_hr_responsibles"
            and l.state == "confirm"
            and l.employee_id
            and not l.responsible_approval_line_ids
        )
        if not to_init:
            return
        to_init._init_responsible_approval_lines()
        to_init.modified(
            ["responsible_approval_line_ids", "employee_id", "holiday_status_id"]
        )

    def _responsible_backfill_pending_since_if_missing(self):
        """Sequential HR Responsibles: active pending step must have pending_since or timeout never runs."""
        for leave in self:
            if leave.validation_type != "employee_hr_responsibles":
                continue
            if leave.holiday_status_id.employee_responsible_approval_mode != "sequential":
                continue
            first = leave.responsible_approval_line_ids.filtered(
                lambda ln: ln.state == "pending"
            ).sorted("sequence")[:1]
            if not first or first.pending_since:
                continue
            hours = leave.holiday_status_id.employee_responsible_escalation_hours or 2.0
            threshold = fields.Datetime.now() - timedelta(hours=hours)
            first.write({"pending_since": threshold - timedelta(seconds=1)})

    def _notify_responsible_approvers_submission(self):
        """FYI notification to all configured approvers when a leave is submitted."""
        self.ensure_one()
        if self.validation_type != "employee_hr_responsibles":
            return
        users = self._get_responsible_approval_users().filtered(
            lambda u: u.partner_id and not u.share
        )
        if not users:
            return
        self.message_post(
            body=_(
                "New time off request from %(employee)s requires your review in the responsible approval flow."
            )
            % {"employee": self.employee_id.name or self.display_name},
            message_type="notification",
            subtype_xmlid="mail.mt_comment",
            partner_ids=users.mapped("partner_id").ids,
        )

    def _notify_responsible_current_turn(self, user=None):
        """Direct notification to the approver whose pending step is currently active."""
        self.ensure_one()
        if self.validation_type != "employee_hr_responsibles":
            return
        line = False
        if user:
            line = self.responsible_approval_line_ids.filtered(
                lambda l: l.state == "pending" and l.user_id == user
            )[:1]
        if not line:
            line = self.responsible_approval_line_ids.filtered(
                lambda l: l.state == "pending"
            ).sorted("sequence")[:1]
        if not line or not line.user_id.partner_id:
            return
        self.message_post(
            body=_(
                "It is now your turn to approve time off request %(leave)s for %(employee)s."
            )
            % {
                "leave": self.display_name,
                "employee": self.employee_id.name or "",
            },
            message_type="notification",
            subtype_xmlid="mail.mt_comment",
            partner_ids=[line.user_id.partner_id.id],
        )

    def action_confirm(self):
        missing_handover = self.filtered(lambda leave: not leave.handover_employee_ids)
        if missing_handover:
            raise UserError(
                _(
                    "Please select at least one work handover recipient before submitting the time off request."
                )
            )
        try:
            res = super().action_confirm()
        except AttributeError:
            res = True
        subset = self.filtered(
            lambda l: l.validation_type == "employee_hr_responsibles" and l.state == "confirm"
        )
        if subset:
            subset._ensure_responsible_approval_lines()
            subset._responsible_backfill_pending_since_if_missing()
            for leave in subset:
                leave._notify_responsible_approvers_submission()
                leave._notify_responsible_current_turn()
        self._bootstrap_handover_workflow()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._apply_emergency_leave_on_vals(vals)
        records = super().create(vals_list)
        records._ensure_responsible_approval_lines()
        records._responsible_backfill_pending_since_if_missing()
        records._bootstrap_handover_workflow()
        return records

    def _check_approval_update(self, state, raise_if_not_possible=True):
        """Demo extension:
        allow extra officers / extra office-departments configured on Time Off Type to approve/refuse.
        """
        if self.env.is_superuser():
            return True

        current_employee = self.env.user.employee_id
        is_officer = self.env.user.has_group("hr_holidays.group_hr_holidays_user")
        is_manager = self.env.user.has_group("hr_holidays.group_hr_holidays_manager")

        for holiday in self:
            if state in ("validate1", "validate", "refuse"):
                blocking = holiday._get_handover_blocking_employees()
                if blocking:
                    if raise_if_not_possible:
                        raise UserError(
                            _(
                                "Approval is locked until all work handover recipients accept. "
                                "Still waiting for: %(names)s."
                            )
                            % {"names": ", ".join(blocking.mapped("name"))}
                        )
                    return False
            val_type = holiday.validation_type
            is_extra_officer = self.env.user in holiday.extra_approver_user_ids
            is_officer_any = is_officer or is_extra_officer

            if val_type == "multi_step_6":
                if not is_manager:
                    approvers = holiday._get_multi_step_approvers()
                    if self.env.user not in approvers:
                        if raise_if_not_possible:
                            raise UserError(_("You are not allowed to approve/refuse this multi-step time off step."))
                        return False
                continue

            if val_type == "employee_hr_responsibles":
                if state in ("validate", "refuse"):
                    if not is_manager and holiday._employee_hr_blocks_self_approval_non_director():
                        if raise_if_not_possible:
                            raise UserError(
                                _(
                                    "In this workflow only employees with job title \"Director\" may approve or refuse "
                                    "their own time off. Other approvers must process someone else's request."
                                )
                            )
                        return False
                    if not is_manager and self.env.user not in holiday._get_responsible_approval_users():
                        if raise_if_not_possible:
                            raise UserError(_("You are not allowed to approve/refuse this leave for current responsible flow."))
                        return False
                continue

            if not is_manager and state != "confirm":
                if state == "draft":
                    if holiday.state == "refuse":
                        raise UserError(_("Only a Time Off Manager can reset a refused leave."))
                    if holiday.date_from and holiday.date_from.date() <= fields.Date.today():
                        raise UserError(_("Only a Time Off Manager can reset a started leave."))
                    if holiday.employee_id != current_employee:
                        raise UserError(_("Only a Time Off Manager can reset other people leaves."))
                else:
                    if val_type == "no_validation" and current_employee == holiday.employee_id and (
                        is_officer_any or is_manager
                    ):
                        continue
                    # use ir.rule based first access check: department, members, ... (see security.xml)
                    holiday.check_access_rule("write")

                    # This handles states validate1 / validate / refuse
                    if (
                        holiday.employee_id == current_employee
                        and self.env.user != holiday.employee_id.leave_manager_id
                        and not is_officer_any
                    ):
                        raise UserError(
                            _("Only a Time Off Officer or Manager can approve/refuse its own requests.")
                        )

                    if (state == "validate1" and val_type == "both") and holiday.employee_id:
                        if not is_officer_any and self.env.user != holiday.employee_id.leave_manager_id:
                            raise UserError(
                                _("You must be either %s's manager or Time off Manager to approve this leave")
                                % (holiday.employee_id.name,)
                            )

                    if (
                        state == "validate"
                        and val_type == "manager"
                        and self.env.user
                        != (holiday.employee_id | holiday.sudo().employee_ids).leave_manager_id
                        and not is_officer_any
                    ):
                        if holiday.employee_id:
                            employees = holiday.employee_id
                        else:
                            employees = ", ".join(
                                holiday.employee_ids.filtered(lambda e: e.leave_manager_id != self.env.user).mapped(
                                    "name"
                                )
                            )
                        raise UserError(_("You must be %s's Manager to approve this leave", employees))

                    if (
                        not is_officer_any
                        and (state == "validate" and val_type == "hr")
                        and holiday.employee_id
                    ):
                        raise UserError(_("You must either be a Time off Officer or Time off Manager to approve this leave"))

        return True

    def action_approve(self, check_state=True):
        self._ensure_handover_ready_for_approval()
        return super().action_approve(check_state=check_state)

    def action_multi_step_approve(self):
        """Approve one multi-step level (demo, fixed 6 steps)."""
        self.ensure_one()
        if self.validation_type != "multi_step_6":
            raise UserError(_("This leave is not configured for multi-step approval."))
        if self.state != "confirm":
            raise UserError(_("Time off must be in 'To Approve' state to approve steps."))
        self._ensure_handover_ready_for_approval()

        approvers = self._get_multi_step_approvers()
        is_manager = self.env.user.has_group("hr_holidays.group_hr_holidays_manager")
        if not is_manager and self.env.user not in approvers:
            raise UserError(_("You are not authorized to approve the current step."))

        step = self._get_current_multi_step()
        if not step:
            raise UserError(_("Missing multi-step configuration for step %s.") % self.multi_step_current)

        if not self._multi_step_previous_steps_logged():
            raise UserError(
                _("Earlier approval steps are missing from the log. Approvals must be done in order (step 1, then 2, …).")
            )

        self.env["hr.leave.multi.approval"].create(
            {
                "leave_id": self.id,
                "step_id": step.id,
                "approver_user_id": self.env.user.id,
            }
        )

        max_seq = max(self.holiday_status_id.multi_approval_step_ids.mapped("sequence") or [1])
        if self.multi_step_current < max_seq:
            self.write({"multi_step_current": self.multi_step_current + 1})
            self.activity_update()
            return True

        return self._action_validate(check_state=False)

    def action_cancel(self):
        """Guard cancel wizard against unsaved dashboard popup records.

        In the calendar popup, users can click "Cancel Time Off" before the leave is actually saved.
        Base wizard needs a persisted leave_id; otherwise it crashes with required field missing.
        """
        self.ensure_one()
        leave_id = self._origin.id or (self.id if isinstance(self.id, Integral) else False)
        if not leave_id:
            return {"type": "ir.actions.act_window_close"}
        return {
            "name": _("Cancel Time Off"),
            "type": "ir.actions.act_window",
            "target": "new",
            "res_model": "hr.holidays.cancel.leave",
            "view_mode": "form",
            "views": [[False, "form"]],
            "context": {
                "default_leave_id": leave_id,
                "dialog_size": "medium",
            },
        }

    def action_multi_step_refuse(self):
        """Refuse a multi-step leave at the current step."""
        self.ensure_one()
        if self.validation_type != "multi_step_6":
            raise UserError(_("This leave is not configured for multi-step approval."))
        if self.state != "confirm":
            raise UserError(_("Time off must be in 'To Approve' state to refuse steps."))
        self._ensure_handover_ready_for_approval()

        approvers = self._get_multi_step_approvers()
        is_manager = self.env.user.has_group("hr_holidays.group_hr_holidays_manager")
        if not is_manager and self.env.user not in approvers:
            raise UserError(_("You are not authorized to refuse the current step."))

        step = self._get_current_multi_step()
        if step:
            self.env["hr.leave.multi.approval"].create(
                {
                    "leave_id": self.id,
                    "step_id": step.id,
                    "approver_user_id": self.env.user.id,
                }
            )

        return super().action_refuse()

    def action_responsible_approve(self):
        self.ensure_one()
        if self.validation_type != "employee_hr_responsibles":
            raise UserError(_("This leave is not configured for Employee HR Responsibles flow."))
        if self.state not in ("confirm", "validate1"):
            raise UserError(_("Time off must be in 'To Approve' or 'Second Approval' state."))
        self._ensure_handover_ready_for_approval()

        is_manager = self.env.user.has_group("hr_holidays.group_hr_holidays_manager")
        is_responsible = self.env.user in self._get_responsible_approval_users()
        mode = self.holiday_status_id.employee_responsible_approval_mode
        if mode == "sequential":
            if not is_responsible:
                raise UserError(_("You are not allowed to approve this leave."))
        elif not is_manager and not is_responsible:
            raise UserError(_("You are not allowed to approve this leave."))
        if (mode == "sequential" or not is_manager) and self._employee_hr_blocks_self_approval_non_director():
            raise UserError(
                _(
                    "Only employees with job title \"Director\" may approve their own time off in this workflow. "
                    "Ask another approver in the chain."
                )
            )

        if not self.responsible_approval_line_ids:
            self._init_responsible_approval_lines()

        user_line = self.responsible_approval_line_ids.filtered(
            lambda l: l.user_id == self.env.user
        )[:1]
        if user_line and user_line.state != "pending":
            raise UserError(_("You already processed your approval for this leave."))

        if mode == "sequential":
            first_pending = self.responsible_approval_line_ids.filtered(
                lambda l: l.state == "pending"
            ).sorted("sequence")[:1]
            if not user_line or not first_pending or user_line != first_pending:
                raise UserError(_("This leave must be approved in sequence order."))

        if is_responsible and user_line:
            user_line.write({"state": "approved", "action_date": fields.Datetime.now()})
            if mode == "sequential":
                next_pending = self.responsible_approval_line_ids.filtered(
                    lambda l: l.state == "pending"
                ).sorted("sequence")[:1]
                if next_pending:
                    next_pending.write({"pending_since": fields.Datetime.now()})
                    self._notify_responsible_current_turn(next_pending.user_id)

        if mode == "any":
            return self._action_validate(check_state=False)

        pending = self.responsible_approval_line_ids.filtered(lambda l: l.state == "pending")
        if not pending:
            return self._action_validate(check_state=False)

        self.activity_update()
        return True

    def action_responsible_refuse(self):
        self.ensure_one()
        if self.validation_type != "employee_hr_responsibles":
            raise UserError(_("This leave is not configured for Employee HR Responsibles flow."))
        if self.state not in ("confirm", "validate1"):
            raise UserError(_("Time off must be in 'To Approve' or 'Second Approval' state."))
        self._ensure_handover_ready_for_approval()

        is_manager = self.env.user.has_group("hr_holidays.group_hr_holidays_manager")
        is_responsible = self.env.user in self._get_responsible_approval_users()
        mode = self.holiday_status_id.employee_responsible_approval_mode
        if mode == "sequential":
            if not is_responsible:
                raise UserError(_("You are not allowed to refuse this leave."))
        elif not is_manager and not is_responsible:
            raise UserError(_("You are not allowed to refuse this leave."))
        if (mode == "sequential" or not is_manager) and self._employee_hr_blocks_self_approval_non_director():
            raise UserError(
                _(
                    "Only employees with job title \"Director\" may refuse their own time off in this workflow. "
                    "Ask another approver in the chain."
                )
            )

        if not self.responsible_approval_line_ids:
            self._init_responsible_approval_lines()

        user_line = self.responsible_approval_line_ids.filtered(
            lambda l: l.user_id == self.env.user
        )[:1]
        if mode == "sequential":
            first_pending = self.responsible_approval_line_ids.filtered(
                lambda l: l.state == "pending"
            ).sorted("sequence")[:1]
            if not user_line or not first_pending or user_line != first_pending:
                raise UserError(_("This leave must be refused in sequence order."))

        if user_line and user_line.state == "pending":
            user_line.write({"state": "refused", "action_date": fields.Datetime.now()})

        return super().action_refuse()

    def action_refuse(self):
        self._ensure_handover_ready_for_approval()
        return super().action_refuse()

    @api.model
    def cron_escalate_responsible_approval_timeouts(self):
        """Sequential Employee HR Responsibles: skip current step after escalation delay (default 2h)."""
        leaves = self.search(
            [
                ("state", "in", ("confirm", "validate1")),
                ("validation_type", "=", "employee_hr_responsibles"),
            ]
        )
        for leave in leaves:
            leave._apply_responsible_timeout_escalation()

    def _apply_responsible_timeout_escalation(self):
        self.ensure_one()
        if self.holiday_status_id.employee_responsible_approval_mode != "sequential":
            return
        if not self.responsible_approval_line_ids:
            return
        hours = self.holiday_status_id.employee_responsible_escalation_hours or 2.0
        threshold = fields.Datetime.now() - timedelta(hours=hours)
        first_pending = self.responsible_approval_line_ids.filtered(
            lambda l: l.state == "pending"
        ).sorted("sequence")[:1]
        if not first_pending:
            return
        if not first_pending.pending_since:
            first_pending.write({"pending_since": threshold - timedelta(seconds=1)})
        if first_pending.pending_since > threshold:
            return
        skipped_user = first_pending.user_id
        first_pending.write(
            {
                "state": "skipped",
                "action_date": fields.Datetime.now(),
            }
        )
        self.message_post(
            body=_(
                "Approval step for %(user)s was skipped due to timeout (%(hours)s h); escalated to the next level."
            )
            % {"user": skipped_user.display_name, "hours": hours},
            subtype_xmlid="mail.mt_note",
        )
        next_pending = self.responsible_approval_line_ids.filtered(
            lambda l: l.state == "pending"
        ).sorted("sequence")[:1]
        if next_pending:
            next_pending.write({"pending_since": fields.Datetime.now()})
            self.activity_update()
            self._notify_responsible_current_turn(next_pending.user_id)
        else:
            self._action_validate(check_state=False)

