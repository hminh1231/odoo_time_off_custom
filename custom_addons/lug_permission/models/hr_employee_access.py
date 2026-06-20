# -*- coding: utf-8 -*-

from odoo import api, models
from odoo.fields import Domain


class HrEmployeeAccessMixin(models.AbstractModel):
    _inherit = "hr.employee.access.mixin"

    @api.model
    def _hr_employee_visibility_read_domain(self, user=None, model_name=None):
        """When LUG is active, enforce visibility_policy strictly.

        The default mixin widens scope via leave_manager_id and every employee
        referenced by a readable hr.leave record. That is useful for legacy
        officer workflows but breaks store/assigned scopes (e.g. ASM only sees
        LUG_KDV but still saw LUG_THD via an old cross-store leave).
        """
        user = user or self.env.user
        if not user.sudo()._lug_permission_is_enforced():
            return super()._hr_employee_visibility_read_domain(
                user, model_name=model_name
            )
        if self._hr_employee_user_has_full_visibility(user):
            return None
        policy = self._hr_employee_policy_domain(user)
        self_only = Domain(
            [
                "|",
                ("user_id", "=", user.id),
                ("id", "=", user.sudo().employee_id.id),
            ]
        )
        company = self._hr_employee_company_domain(user)
        if policy is None:
            return self_only & company
        return (policy | self_only) & company

    @api.model
    def _hr_employee_leave_approval_emp_ids(self, user=None):
        user = user or self.env.user
        if not user.sudo()._lug_permission_is_enforced():
            return super()._hr_employee_leave_approval_emp_ids(user)
        return []
