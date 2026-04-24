# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    job_title = fields.Selection(
        related="employee_id.job_title",
        export_string_translation=False,
    )
