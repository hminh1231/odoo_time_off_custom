# -*- coding: utf-8 -*-

from odoo import api, fields, models


class HrStorePlace(models.Model):
    _name = 'hr.store.place'
    _description = 'Store Place'
    _order = 'sequence, name, id'

    name = fields.Char(string='Tên địa điểm', required=True, translate=True)
    code = fields.Char(string='Mã địa điểm')
    sequence = fields.Integer(string='Thứ tự', default=10)
    active = fields.Boolean(string='Có hiệu lực', default=True)
    description = fields.Text(string='Ghi chú')

    store_ids = fields.One2many(
        'hr.store',
        'store_place_id',
        string='Cửa hàng',
    )
    store_count = fields.Integer(
        string='Số cửa hàng',
        compute='_compute_store_count',
    )

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Tên Store Place phải là duy nhất!'),
    ]

    @api.depends('store_ids')
    def _compute_store_count(self):
        for place in self:
            place.store_count = len(place.store_ids)

    def action_view_stores(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('hr_store.hr_store_action')
        action['domain'] = [('store_place_id', '=', self.id)]
        action['context'] = dict(
            self.env.context,
            default_store_place_id=self.id,
        )
        return action
