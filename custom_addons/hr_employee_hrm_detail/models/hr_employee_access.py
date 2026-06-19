# -*- coding: utf-8 -*-

from odoo import api, models
from odoo.fields import Domain


class HrEmployeeAccessMixin(models.AbstractModel):
    _name = "hr.employee.access.mixin"
    _description = "Employee visibility access helpers (visibility_policy based)"

    @api.model
    def _hr_employee_access_self_domain(self, user=None):
        """Always visible: own record + records the user approves time off for.

        The leave_manager_id clause keeps the Time Off approval workflow working
        regardless of the visibility policy (a Leader must read the requester).
        Field names are identical on hr.employee and hr.employee.public.
        """
        user = user or self.env.user
        return Domain([
            "|", "|",
            ("user_id", "=", user.id),
            ("id", "=", user.employee_id.id),
            ("leave_manager_id", "=", user.id),
        ])

    @api.model
    def _hr_employee_company_domain(self, user=None):
        user = user or self.env.user
        return Domain([("company_id", "in", user.company_ids.ids + [False])])

    @api.model
    def _hr_employee_user_has_full_visibility(self, user=None):
        user = user or self.env.user
        return (
            user._is_superuser()
            or user.has_group("hr.group_hr_manager")
            or (user.visibility_policy or "self") == "all"
        )

    @api.model
    def _hr_employee_policy_domain(self, user=None):
        """Core domain for the selected visibility_policy (excluding self/company)."""
        user = user or self.env.user
        policy = user.visibility_policy or "self"
        if policy == "ma_bo_phan":
            code = user.sudo().employee_ma_bo_phan_id
            if not code:
                return None
            return Domain([("ma_bo_phan_id", "=", code.id)])
        if policy == "assigned":
            code_ids = user.sudo().assigned_ma_bo_phan_ids.ids
            if not code_ids:
                return None
            return Domain([("ma_bo_phan_id", "in", code_ids)])
        if policy == "department":
            dept = user.sudo().employee_department_id
            if not dept:
                return None
            return Domain([("department_id", "=", dept.id)])
        if policy == "region":
            mien = user.sudo().employee_mien
            if not mien:
                return None
            return Domain([("mien", "=", mien)])
        # 'self' (and any unknown value) -> no extra rows beyond self domain
        return None

    @api.model
    def _hr_employee_visibility_read_domain(self, user=None, model_name=None):
        """Return None when unrestricted, else the AND-able read domain."""
        user = user or self.env.user
        if self._hr_employee_user_has_full_visibility(user):
            return None
        self_domain = self._hr_employee_access_self_domain(user)
        company_domain = self._hr_employee_company_domain(user)
        policy_domain = self._hr_employee_policy_domain(user)
        if policy_domain is None:
            return self_domain & company_domain
        return (policy_domain | self_domain) & company_domain

    # Backwards-compatible aliases used elsewhere in the module.
    @api.model
    def _hr_employee_access_scope_domain(self, user=None, model_name=None):
        return self._hr_employee_access_self_domain(user)

    @api.model
    def _hr_employee_access_extra_domain(self, user=None, model_name=None):
        user = user or self.env.user
        return self._hr_employee_visibility_read_domain(user, model_name=model_name)

    @api.model
    def _hr_employee_apply_access_domain(self, domain, model_name=None):
        extra = self._hr_employee_access_extra_domain(model_name=model_name)
        if extra is not None:
            return Domain(domain) & extra
        return Domain(domain)

    @api.model
    def _hr_employee_discuss_access_applies(self, user=None):
        """Discuss / chat must never follow HR employee visibility."""
        return False
