# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    personal_tab_hidden_for_privacy = fields.Boolean(
        compute="_compute_personal_tab_hidden_for_privacy",
        help="When true, the Personal tab is hidden (Employees=No and viewing another employee).",
    )

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
