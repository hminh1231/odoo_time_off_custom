from odoo import api, models, _


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    @api.model
    def get_allocation_requests_amount(self):
        """Count pending time-off leave requests (confirm / validate1) instead of allocation requests."""
        employee = self._get_contextual_employee()
        return self.env["hr.leave"].search_count([
            ("employee_id", "=", employee.id),
            ("state", "in", ("confirm", "validate1")),
        ])

    @api.model
    def get_time_off_dashboard_data(self, target_date=None):
        result = super().get_time_off_dashboard_data(target_date=target_date)
        employee = self._get_contextual_employee().sudo()
        result["da_su_dung"] = employee.da_su_dung if employee else 0.0
        result["con_lai"] = employee.con_lai if employee else 0.0
        return result
