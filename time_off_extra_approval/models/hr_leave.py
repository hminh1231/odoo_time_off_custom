from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
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
    approval_current_step_label = fields.Char(
        string="Current approval",
        compute="_compute_approval_current_step_label",
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

        for leave in self:
            if not leave.id or leave.state not in ("confirm", "validate1"):
                leave.approval_actionable_user_ids = Users
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

    def write(self, vals):
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
        return res

    @api.depends("validation_type", "state", "multi_step_current", "holiday_status_id")
    def _compute_can_multi_step_approve(self):
        for leave in self:
            can = False
            if leave.validation_type == "multi_step_6" and leave.state == "confirm":
                is_manager = leave.env.user.has_group("hr_holidays.group_hr_holidays_manager")
                if is_manager:
                    can = True
                else:
                    can = leave.env.user in leave._get_multi_step_approvers()
            leave.can_multi_step_approve = can

    @api.depends("state", "employee_id", "department_id", "holiday_status_id")
    def _compute_can_approve(self):
        super()._compute_can_approve()
        for leave in self.filtered(
            lambda h: h.validation_type in ("employee_hr_responsibles", "multi_step_6")
        ):
            leave.can_approve = False

    @api.depends("state", "employee_id", "department_id", "holiday_status_id")
    def _compute_can_validate(self):
        super()._compute_can_validate()
        for leave in self.filtered(
            lambda h: h.validation_type in ("employee_hr_responsibles", "multi_step_6")
        ):
            leave.can_validate = False

    @api.depends("state", "employee_id", "department_id", "holiday_status_id")
    def _compute_can_refuse(self):
        super()._compute_can_refuse()
        for leave in self.filtered(
            lambda h: h.validation_type in ("employee_hr_responsibles", "multi_step_6")
        ):
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

    def action_confirm(self):
        res = super().action_confirm()
        subset = self.filtered(
            lambda l: l.validation_type == "employee_hr_responsibles" and l.state == "confirm"
        )
        if subset:
            subset._ensure_responsible_approval_lines()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_responsible_approval_lines()
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

    def action_multi_step_approve(self):
        """Approve one multi-step level (demo, fixed 6 steps)."""
        self.ensure_one()
        if self.validation_type != "multi_step_6":
            raise UserError(_("This leave is not configured for multi-step approval."))
        if self.state != "confirm":
            raise UserError(_("Time off must be in 'To Approve' state to approve steps."))

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

    def action_multi_step_refuse(self):
        """Refuse a multi-step leave at the current step."""
        self.ensure_one()
        if self.validation_type != "multi_step_6":
            raise UserError(_("This leave is not configured for multi-step approval."))
        if self.state != "confirm":
            raise UserError(_("Time off must be in 'To Approve' state to refuse steps."))

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

    @api.model
    def cron_escalate_responsible_approval_timeouts(self):
        """Sequential Employee HR Responsibles: skip current step after escalation delay (default 2h)."""
        leaves = self.search(
            [
                ("state", "=", "confirm"),
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
        if not first_pending or not first_pending.pending_since:
            return
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
        else:
            self._action_validate(check_state=False)

