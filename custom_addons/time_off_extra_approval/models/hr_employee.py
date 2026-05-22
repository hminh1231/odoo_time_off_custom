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
