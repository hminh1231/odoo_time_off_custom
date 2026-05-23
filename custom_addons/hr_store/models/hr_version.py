# -*- coding: utf-8 -*-

from odoo import fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    store_id = fields.Many2one(
        'hr.store',
        string='Cửa hàng',
        check_company=True,
        tracking=True,
        index=True,
    )
