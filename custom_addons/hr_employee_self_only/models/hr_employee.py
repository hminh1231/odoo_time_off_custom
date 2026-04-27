# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models

from .hr_employee_privacy import (
    _privacy_raise_if_employee_create_forbidden,
    _privacy_raise_if_employee_no_write,
)


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _check_employees_no_readonly(self):
        _privacy_raise_if_employee_no_write(self.env, self)

    personal_tab_hidden_for_privacy = fields.Boolean(
        compute="_compute_personal_tab_hidden_for_privacy",
        help="When true, the Personal tab is hidden (Employees=No and viewing another employee).",
    )
    employee_form_force_readonly_ui = fields.Boolean(
        compute="_compute_employee_form_force_readonly_ui",
        help="When true, employee form opens in readonly mode (Employees privilege: No).",
    )

    @api.depends_context("uid")
    def _compute_employee_form_force_readonly_ui(self):
        user = self.env.user
        lock = user.has_group(
            "hr_employee_self_only.group_hr_employees_no"
        ) and not user.has_group("hr.group_hr_manager")
        for emp in self:
            emp.employee_form_force_readonly_ui = lock

    @api.depends("user_id", "name")
    def _compute_personal_tab_hidden_for_privacy(self):
        user = self.env.user
        if user.has_group("hr.group_hr_manager"):
            for emp in self:
                emp.personal_tab_hidden_for_privacy = False
            return
        if not user.has_group("hr_employee_self_only.group_hr_employees_no"):
            for emp in self:
                emp.personal_tab_hidden_for_privacy = False
            return
        own = user.employee_id
        own_id = own.id if own else False
        for emp in self:
            if not own_id:
                emp.personal_tab_hidden_for_privacy = True
            else:
                emp.personal_tab_hidden_for_privacy = emp.id != own_id

    @api.model_create_multi
    def create(self, vals_list):
        _privacy_raise_if_employee_create_forbidden(self.env)
        return super().create(vals_list)

    def write(self, vals):
        self._check_employees_no_readonly()
        return super().write(vals)

    def unlink(self):
        self._check_employees_no_readonly()
        return super().unlink()
