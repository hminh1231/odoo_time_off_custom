# -*- coding: utf-8 -*-

from odoo import fields, models


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    store_id = fields.Many2one(
        'hr.store',
        related='employee_id.store_id',
        readonly=True,
    )
