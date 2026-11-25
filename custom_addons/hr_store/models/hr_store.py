# -*- coding: utf-8 -*-

from odoo import api, fields, models


class HrStore(models.Model):
    _name = 'hr.store'
    _description = 'Store'
    _order = 'name'

    name = fields.Char(string='Tên cửa hàng', required=True, translate=True)
    code = fields.Char(string='Mã cửa hàng', help='Mã nội bộ, ví dụ: CH-Q1')
    mien = fields.Selection(
        selection=[
            ('Bắc', 'Bắc'),
            ('Nam', 'Nam'),
            ('ĐTT', 'ĐTT'),
            ('VP', 'VP'),
        ],
        string='Miền',
    )
    store_place = fields.Selection(
        selection=[
            ('GO', 'GO'),
            ('TTTM', 'TTTM'),
            ('AEON', 'AEON'),
            ('Mặt phố', 'Mặt phố'),
        ],
        string='Store Place',
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )
    manager_id = fields.Many2one(
        'hr.employee',
        string='Quản lý cửa hàng',
        ondelete='set null',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    street = fields.Char(string='Street')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State', domain="[('country_id', '=?', country_id)]")
    country_id = fields.Many2one('res.country', string='Country')
    phone = fields.Char(string='Phone')
    note = fields.Text(string='Note')
    color = fields.Integer(string='Color Index')
    member_ids = fields.One2many('hr.employee', 'store_id', string='Employees', readonly=True)
    total_employee = fields.Integer(compute='_compute_total_employee', string='Total Employees')

    @api.depends('member_ids')
    def _compute_total_employee(self):
        for store in self:
            store.total_employee = len(store.member_ids)

    def action_employee_from_store(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('hr.open_view_employee_list_my')
        action['domain'] = [('store_id', '=', self.id)]
        action['context'] = dict(
            self.env.context,
            default_store_id=self.id,
        )
        return action

    @api.readonly
    def web_read(self, specification: dict[str, dict]) -> list[dict]:
        try:
            return super().web_read(specification)
        except KeyError:
            # Fallback 1: If a related record (e.g. manager_id of another mien/dept)
            # is restricted by ir.rule, read as sudo so display_name/avatar is retrieved safely
            if not self.env.su:
                try:
                    return self.sudo().web_read(specification)
                except KeyError:
                    pass
            # Fallback 2: If a comodel record was deleted from DB (orphaned foreign key),
            # sanitize specification to avoid resolving missing foreign keys:
            clean_spec = dict(specification)
            for fname, fspec in list(clean_spec.items()):
                f = self._fields.get(fname)
                if f and f.type == 'many2one' and isinstance(fspec, dict) and 'fields' in fspec:
                    clean_spec[fname] = {}
            return super(HrStore, self.sudo()).web_read(clean_spec)

