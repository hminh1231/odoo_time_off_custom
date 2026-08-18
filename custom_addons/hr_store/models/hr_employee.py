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
    managed_store_ids = fields.Many2many(
        'hr.store',
        'hr_employee_managed_store_rel',
        'employee_id',
        'store_id',
        string='Cửa hàng quản lí',
        tracking=True,
        help='Các cửa hàng mà nhân viên này quản lí.',
    )
