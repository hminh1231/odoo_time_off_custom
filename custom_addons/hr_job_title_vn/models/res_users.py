from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    job_title = fields.Selection(related="employee_id.job_title")
