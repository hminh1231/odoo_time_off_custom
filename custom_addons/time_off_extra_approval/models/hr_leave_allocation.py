from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

_MULTI_STEP_ALLOC_RESET_CTX = "time_off_alloc_multi_step_reset_skip"


class HolidaysAllocation(models.Model):
    _inherit = "hr.leave.allocation"

    # Multi-step approval (demo) used when hr.leave.type.allocation_validation_type == 'multi_step_6'.
    multi_step_current = fields.Integer(
        string="Multi-step Current Step",
        default=1,
        help="Current approval step index (1..6) for multi-step allocation approval (demo).",
    )
    multi_approval_line_ids = fields.One2many(
        comodel_name="hr.leave.multi.approval",
        inverse_name="allocation_id",
        string="Multi-step Approval Log (Demo)",
        readonly=True,
    )
    can_multi_step_validate = fields.Boolean(
        string="Can Validate Current Multi-step (Demo)",
        compute="_compute_can_multi_step_validate",
    )

    extra_approver_user_ids = fields.Many2many(
        comodel_name="res.users",
        relation="hr_leave_allocation_extra_approver_user_rel",
        column1="allocation_id",
        column2="user_id",
        string="Extra Time Off Allocation Approvers",
        compute="_compute_extra_approver_user_ids",
        store=True,
        readonly=True,
        help="Users who can approve/refuse allocations based on the leave type configuration.",
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
        for allocation in self:
            if allocation.validation_type == "multi_step_6":
                step = allocation._get_current_multi_step()
                allocation.extra_approver_user_ids = step and step._get_all_approver_users() or self.env["res.users"]
                continue

            users = allocation.holiday_status_id.extra_responsible_user_ids
            if allocation.holiday_status_id.extra_responsible_department_ids:
                dept_users = allocation.holiday_status_id.extra_responsible_department_ids.mapped(
                    "member_ids.user_id"
                )
                dept_users = dept_users.filtered(lambda u: u and not u.share)
                users |= dept_users
            allocation.extra_approver_user_ids = users

    def _get_current_multi_step(self):
        self.ensure_one()
        if self.validation_type != "multi_step_6":
            return self.env["hr.leave.type.approval.step"]
        steps = self.holiday_status_id.multi_approval_step_ids
        return steps.filtered(lambda s: s.sequence == self.multi_step_current)[:1]

    def _get_multi_step_approvers(self):
        self.ensure_one()
        step = self._get_current_multi_step()
        return step and step._get_all_approver_users() or self.env["res.users"]

    def _multi_step_previous_steps_logged(self):
        self.ensure_one()
        if self.multi_step_current <= 1:
            return True
        done_seqs = set(self.multi_approval_line_ids.mapped("step_id.sequence"))
        needed = set(range(1, self.multi_step_current))
        return needed.issubset(done_seqs)

    def write(self, vals):
        reset_recs = self.env["hr.leave.allocation"]
        if vals.get("state") == "confirm" and not self.env.context.get(_MULTI_STEP_ALLOC_RESET_CTX):
            reset_recs = self.filtered(
                lambda a: a.validation_type == "multi_step_6" and a.state != "confirm"
            )
        res = super().write(vals)
        if reset_recs:
            reset_recs.mapped("multi_approval_line_ids").unlink()
            reset_recs.with_context(**{_MULTI_STEP_ALLOC_RESET_CTX: True}).write({"multi_step_current": 1})
        return res

    @api.depends("validation_type", "state", "multi_step_current", "holiday_status_id")
    def _compute_can_multi_step_validate(self):
        for allocation in self:
            can = False
            if allocation.validation_type == "multi_step_6" and allocation.state == "confirm":
                is_manager = allocation.env.user.has_group("hr_holidays.group_hr_holidays_manager")
                if is_manager:
                    can = True
                else:
                    can = allocation.env.user in allocation._get_multi_step_approvers()
            allocation.can_multi_step_validate = can

    def _check_approval_update(self, state, raise_if_not_possible=True):
        """Demo extension:
        Allow approval/refusal for extra officers/offices depending on
        `hr.leave.type.allocation_validation_type` (officer/manager/leader).
        """
        if self.env.is_superuser():
            return True

        current_employee = self.env.user.employee_id
        if not current_employee:
            return super()._check_approval_update(state, raise_if_not_possible=raise_if_not_possible)

        is_officer = self.env.user.has_group("hr_holidays.group_hr_holidays_user")
        is_manager = self.env.user.has_group("hr_holidays.group_hr_holidays_manager")

        for allocation in self:
            if state == "confirm":
                continue

            val_type = allocation.holiday_status_id.sudo().allocation_validation_type
            if val_type == "no":
                continue

            if val_type == "multi_step_6":
                if not is_manager and self.env.user not in allocation._get_multi_step_approvers():
                    if raise_if_not_possible:
                        raise UserError(_("You are not allowed to validate/refuse this multi-step allocation step."))
                    return False
                continue

            is_leave_manager = self.env.user == allocation.employee_id.leave_manager_id
            is_extra = self.env.user in allocation.extra_approver_user_ids

            # Allowed depending on type
            allowed = False
            if val_type == "officer":
                # Standard behavior: officer group OR responsible manager OR extra approvers.
                allowed = is_officer or is_leave_manager or is_extra
            elif val_type == "manager":
                allowed = is_leave_manager or is_officer
            elif val_type == "leader":
                allowed = is_extra or is_officer
            else:
                allowed = is_officer or is_leave_manager or is_extra

            if not allowed:
                raise UserError(
                    _("Only authorized officers/managers/leaders can approve or refuse time off allocations for this type.")
                )

            # First access check: department, members, ... (see security.xml & record rules)
            if is_officer or is_leave_manager or is_extra:
                allocation.check_access_rule("write")

            # Self-approval protection
            if (
                allocation.employee_id == current_employee
                and not is_manager
                and val_type != "no"
            ):
                raise UserError(_("Only a time off Manager can approve its own requests."))

    def _get_responsible_for_approval(self):
        self.ensure_one()
        responsible = self.env["res.users"]

        if self.validation_type == "multi_step_6":
            return self._get_multi_step_approvers()

        if self.validation_type == "officer" or self.validation_type == "set":
            # Standard: time off officers configured on the type.
            responsible = self.holiday_status_id.responsible_ids or self.env.user
            responsible |= self.extra_approver_user_ids
        elif self.validation_type == "manager":
            responsible = self.employee_id.leave_manager_id
        elif self.validation_type == "leader":
            responsible = self.extra_approver_user_ids
        else:
            # Fallback to the standard behavior.
            responsible = super()._get_responsible_for_approval()

        return responsible

    def action_multi_step_validate(self):
        """Approve current multi-step allocation level (demo, fixed 6 steps)."""
        self.ensure_one()
        if self.validation_type != "multi_step_6":
            raise UserError(_("This allocation is not configured for multi-step approval."))
        if self.state != "confirm":
            raise UserError(_("Allocation must be in 'To Approve' state to validate steps."))

        approvers = self._get_multi_step_approvers()
        is_manager = self.env.user.has_group("hr_holidays.group_hr_holidays_manager")
        if not is_manager and self.env.user not in approvers:
            raise UserError(_("You are not authorized to validate the current step."))

        step = self._get_current_multi_step()
        if not step:
            raise UserError(_("Missing multi-step configuration for step %s.") % self.multi_step_current)

        if not self._multi_step_previous_steps_logged():
            raise UserError(
                _("Earlier approval steps are missing from the log. Validations must be done in order (step 1, then 2, …).")
            )

        self.env["hr.leave.multi.approval"].create(
            {
                "allocation_id": self.id,
                "step_id": step.id,
                "approver_user_id": self.env.user.id,
            }
        )

        max_seq = max(self.holiday_status_id.multi_approval_step_ids.mapped("sequence") or [1])
        if self.multi_step_current < max_seq:
            self.write({"multi_step_current": self.multi_step_current + 1})
            self.activity_update()
            return True

        return self._action_validate()

    def action_multi_step_refuse(self):
        """Refuse a multi-step allocation at the current step."""
        self.ensure_one()
        if self.validation_type != "multi_step_6":
            raise UserError(_("This allocation is not configured for multi-step approval."))
        if self.state != "confirm":
            raise UserError(_("Allocation must be in 'To Approve' state to refuse steps."))

        approvers = self._get_multi_step_approvers()
        is_manager = self.env.user.has_group("hr_holidays.group_hr_holidays_manager")
        if not is_manager and self.env.user not in approvers:
            raise UserError(_("You are not authorized to refuse the current step."))

        step = self._get_current_multi_step()
        if step:
            self.env["hr.leave.multi.approval"].create(
                {
                    "allocation_id": self.id,
                    "step_id": step.id,
                    "approver_user_id": self.env.user.id,
                }
            )
        return super().action_refuse()

    def activity_update(self):
        """Override to notify responsible users for officer/manager/leader types."""
        to_clean, to_do = self.env["hr.leave.allocation"], self.env["hr.leave.allocation"]
        activity_vals = []
        for allocation in self:
            if allocation.validation_type != "no":
                note = _(
                    "New Allocation Request created by %(user)s: %(count)s Days of %(allocation_type)s",
                    user=allocation.create_uid.name,
                    count=allocation.number_of_days,
                    allocation_type=allocation.holiday_status_id.name,
                )
                activity_type = self.env.ref("hr_holidays.mail_act_leave_allocation_approval")

                if allocation.state == "confirm":
                    user_ids = allocation.sudo()._get_responsible_for_approval().ids
                    for user_id in user_ids:
                        activity_vals.append(
                            {
                                "activity_type_id": activity_type.id,
                                "automated": True,
                                "note": note,
                                "user_id": user_id,
                                "res_id": allocation.id,
                                "res_model_id": self.env["ir.model"]._get_id("hr.leave.allocation"),
                            }
                        )
                elif allocation.state == "validate":
                    to_do += allocation
                elif allocation.state == "refuse":
                    to_clean += allocation

        if activity_vals:
            self.env["mail.activity"].create(activity_vals)
        if to_clean:
            to_clean.activity_unlink(["hr_holidays.mail_act_leave_allocation_approval"])
        if to_do:
            to_do.activity_feedback(["hr_holidays.mail_act_leave_allocation_approval"])

