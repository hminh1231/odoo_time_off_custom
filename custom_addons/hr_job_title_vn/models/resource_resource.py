from odoo import fields, models


class ResourceResource(models.Model):
    _inherit = "resource.resource"

    job_title = fields.Selection(related="employee_id.job_title")
