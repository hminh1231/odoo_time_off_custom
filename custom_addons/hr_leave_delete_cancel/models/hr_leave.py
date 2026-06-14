# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import UserError

GROUP_LEAVE_DELETE = "hr_leave_delete_cancel.group_hr_holidays_leave_delete"
GROUP_LEAVE_CANCEL = "hr_leave_delete_cancel.group_hr_holidays_leave_cancel"


class HrLeave(models.Model):
    _inherit = "hr.leave"

    def _has_leave_delete_permission(self):
        user = self.env.user
        return user._is_superuser() or user.has_group(GROUP_LEAVE_DELETE)

    def _has_leave_cancel_permission(self):
        user = self.env.user
        return user._is_superuser() or user.has_group(GROUP_LEAVE_CANCEL)

    def _leave_has_handover_acceptance(self, leave):
        leave.ensure_one()
        if "handover_acceptance_ids" not in leave._fields:
            return False
        return bool(
            leave.sudo().handover_acceptance_ids.filtered(lambda line: line.state == "accepted")
        )

    def _is_own_leave_record(self, leave):
        return bool(leave.employee_id) and leave.employee_id in self.env.user.employee_ids

    def _can_cancel_own_leave_strict(self, leave):
        """Without privilege: own leave in confirm before any handover acceptance."""
        if not self._is_own_leave_record(leave):
            return False
        if leave.state != "confirm":
            return False
        if self._leave_has_handover_acceptance(leave):
            return False
        return True

    def _user_can_cancel_leave_record(self, leave):
        if self._has_leave_cancel_permission():
            return True
        return self._can_cancel_own_leave_strict(leave)

    def _raise_leave_cancel_permission_error(self, leave):
        if self._is_own_leave_record(leave):
            if self._leave_has_handover_acceptance(leave):
                raise UserError(
                    _(
                        "You cannot cancel this time off request after work handover has been accepted."
                    )
                )
            raise UserError(
                _(
                    "You can only cancel your own time off request while it is waiting for approval and before work handover is accepted."
                )
            )
        raise UserError(_("You are not allowed to cancel time off requests of employees."))

    def _check_leave_delete_permission(self):
        """Block deleting other employees' time off without explicit permission."""
        if self._has_leave_delete_permission():
            return
        user_employees = self.env.user.employee_ids
        if any(not leave.employee_id or leave.employee_id not in user_employees for leave in self):
            raise UserError(
                _("You are not allowed to delete time off requests of employees.")
            )

    def _check_leave_cancel_permission(self):
        for leave in self:
            if not self._user_can_cancel_leave_record(leave):
                self._raise_leave_cancel_permission_error(leave)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_leave_delete_permission(self):
        self._check_leave_delete_permission()

    @api.depends_context("uid")
    @api.depends("state", "employee_id", "handover_acceptance_ids.state")
    def _compute_can_cancel(self):
        if self.env.user._is_superuser() or self._has_leave_cancel_permission():
            return super()._compute_can_cancel()
        for holiday in self:
            holiday.can_cancel = self._can_cancel_own_leave_strict(holiday)

    @api.depends_context("uid")
    @api.depends("state", "employee_id", "handover_acceptance_ids.state")
    def _compute_can_back_to_approve(self):
        if self.env.user._is_superuser() or self._has_leave_cancel_permission():
            return super()._compute_can_back_to_approve()
        for holiday in self:
            holiday.can_back_to_approve = False

    @api.model
    def _check_approval_update(self, state, raise_if_not_possible=True):
        result = super()._check_approval_update(
            state, raise_if_not_possible=raise_if_not_possible
        )
        if not result or self.env.is_superuser():
            return result
        if state == "cancel":
            for holiday in self:
                if not self._user_can_cancel_leave_record(holiday):
                    if raise_if_not_possible:
                        self._raise_leave_cancel_permission_error(holiday)
                    return False
        elif state == "confirm":
            for holiday in self:
                if (
                    holiday.state == "validate"
                    and not self._user_can_cancel_leave_record(holiday)
                ):
                    if raise_if_not_possible:
                        raise UserError(
                            _(
                                "You are not allowed to reset time off requests of employees to approval."
                            )
                        )
                    return False
        return result

    def action_back_to_approval(self):
        self._check_leave_cancel_permission()
        return super().action_back_to_approval()

    def _action_user_cancel(self, reason=None):
        self._check_leave_cancel_permission()
        return super()._action_user_cancel(reason=reason)

    def _get_next_states_by_state(self):
        self.ensure_one()
        state_result = super()._get_next_states_by_state()
        if self._has_leave_cancel_permission():
            return state_result
        if self._is_own_leave_record(self):
            for states in state_result.values():
                states.discard("cancel")
            if self._can_cancel_own_leave_strict(self):
                state_result["confirm"].add("cancel")
            return state_result
        for states in state_result.values():
            states.discard("cancel")
        return state_result
