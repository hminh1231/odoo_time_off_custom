from odoo import fields, models


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    job_title = fields.Selection(related="employee_id.job_title")
