# -*- coding: utf-8 -*-

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    store_id = fields.Many2one(
        'hr.store',
        string='Cửa hàng',
        index=True,
        tracking=True,
        help='Cửa hàng mà nhân viên thuộc về.',
    )
