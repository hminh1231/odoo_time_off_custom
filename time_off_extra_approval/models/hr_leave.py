from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

_MULTI_STEP_RESET_CTX = "time_off_multi_step_reset_skip"


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

    @api.depends(
        "holiday_status_id",
        "holiday_status_id.extra_responsible_user_ids",
        "holiday_status_id.extra_responsible_department_ids",
        "validation_type",
        "multi_step_current",
        "holiday_status_id.multi_approval_step_ids",
        "holiday_status_id.multi_approval_step_ids.approver_user_id",
        "holiday_status_id.multi_approval_step_ids.approver_user_ids",
        "holiday_status_id.multi_approval_step_ids.approver_department_ids",
    )
    def _compute_extra_approver_user_ids(self):
        for leave in self:
            if leave.validation_type == "multi_step_6":
                step = leave._get_current_multi_step()
                leave.extra_approver_user_ids = step and step._get_all_approver_users() or self.env["res.users"]
                continue

            users = leave.holiday_status_id.extra_responsible_user_ids
            if leave.holiday_status_id.extra_responsible_department_ids:
                dept_users = leave.holiday_status_id.extra_responsible_department_ids.mapped("member_ids.user_id")
                dept_users = dept_users.filtered(lambda u: u and not u.share)
                users |= dept_users
            leave.extra_approver_user_ids = users

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

    def _is_extra_approver(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        return user in self.extra_approver_user_ids

    def _get_responsible_for_approval(self):
        if self.validation_type == "employee_hr_responsibles":
            return self._get_employee_responsible_users()
        if self.validation_type == "multi_step_6":
            return self._get_multi_step_approvers()

        res = super()._get_responsible_for_approval()
        # Only HR-step validations use responsible_ids; for manager validations this is handled by employee leave manager.
        if self.employee_id and (
            self.validation_type == "hr" or (self.validation_type == "both" and self.state == "validate1")
        ):
            res |= self.extra_approver_user_ids
        return res

    @api.depends("validation_type", "state", "responsible_approval_line_ids.state")
    def _compute_can_responsible_approve(self):
        for leave in self:
            can = False
            if leave.validation_type == "employee_hr_responsibles" and leave.state == "confirm":
                if leave.env.user.has_group("hr_holidays.group_hr_holidays_manager"):
                    can = True
                elif leave.env.user in leave._get_employee_responsible_users():
                    mode = leave.holiday_status_id.employee_responsible_approval_mode
                    if mode == "sequential":
                        user_line = leave.responsible_approval_line_ids.filtered(
                            lambda l: l.user_id == leave.env.user and l.state == "pending"
                        )[:1]
                        first_pending = leave.responsible_approval_line_ids.filtered(
                            lambda l: l.state == "pending"
                        ).sorted("sequence")[:1]
                        can = bool(user_line and first_pending and user_line == first_pending)
                    else:
                        can = bool(
                            leave.responsible_approval_line_ids.filtered(
                                lambda l: l.user_id == leave.env.user and l.state == "pending"
                            )[:1]
                        )
            leave.can_responsible_approve = can

    def _init_responsible_approval_lines(self):
        line_model = self.env["hr.leave.responsible.approval"].sudo()
        for leave in self:
            if leave.validation_type != "employee_hr_responsibles" or not leave.employee_id:
                continue
            if leave.responsible_approval_line_ids:
                continue
            approvers = leave._get_employee_responsible_users().sorted("id")
            if not approvers:
                raise UserError(_("This employee has no HR Responsible configured."))
            if len(approvers) > 6:
                raise UserError(_("This workflow supports up to 6 HR Responsibles per employee."))
            for sequence, user in enumerate(approvers, start=1):
                line_model.create(
                    {
                        "leave_id": leave.id,
                        "user_id": user.id,
                        "sequence": sequence,
                    }
                )

    def action_confirm(self):
        res = super().action_confirm()
        self.filtered(lambda l: l.validation_type == "employee_hr_responsibles" and l.state == "confirm")._init_responsible_approval_lines()
        return res

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
                    if not is_manager and self.env.user not in holiday._get_employee_responsible_users():
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
        if self.state != "confirm":
            raise UserError(_("Time off must be in 'To Approve' state."))

        is_manager = self.env.user.has_group("hr_holidays.group_hr_holidays_manager")
        is_responsible = self.env.user in self._get_employee_responsible_users()
        if not is_manager and not is_responsible:
            raise UserError(_("You are not allowed to approve this leave."))

        mode = self.holiday_status_id.employee_responsible_approval_mode
        if not self.responsible_approval_line_ids:
            self._init_responsible_approval_lines()

        user_line = self.responsible_approval_line_ids.filtered(
            lambda l: l.user_id == self.env.user
        )[:1]
        if is_responsible and user_line and user_line.state != "pending":
            raise UserError(_("You already processed your approval for this leave."))

        if mode == "sequential" and is_responsible:
            first_pending = self.responsible_approval_line_ids.filtered(
                lambda l: l.state == "pending"
            ).sorted("sequence")[:1]
            if not user_line or not first_pending or user_line != first_pending:
                raise UserError(_("This leave must be approved in sequence order."))

        if is_responsible and user_line:
            user_line.write({"state": "approved", "action_date": fields.Datetime.now()})

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
        if self.state != "confirm":
            raise UserError(_("Time off must be in 'To Approve' state."))

        is_manager = self.env.user.has_group("hr_holidays.group_hr_holidays_manager")
        is_responsible = self.env.user in self._get_employee_responsible_users()
        if not is_manager and not is_responsible:
            raise UserError(_("You are not allowed to refuse this leave."))

        user_line = self.responsible_approval_line_ids.filtered(
            lambda l: l.user_id == self.env.user
        )[:1]
        if is_responsible and user_line and user_line.state == "pending":
            user_line.write({"state": "refused", "action_date": fields.Datetime.now()})

        return super().action_refuse()

