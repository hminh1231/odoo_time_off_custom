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
    store_place_id = fields.Many2one(
        'hr.store.place',
        string='Store Place',
        ondelete='set null',
        index=True,
        tracking=True,
        help='Địa điểm/loại mặt bằng cửa hàng (nguồn cấu hình chuẩn).',
    )
    store_place = fields.Char(
        string='Store Place (Tên)',
        compute='_compute_store_place',
        inverse='_inverse_store_place',
        store=True,
        help='Tên Store Place để tương thích ngược.',
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )
    manager_ids = fields.Many2many(
        'hr.employee',
        'hr_employee_managed_store_rel',
        'store_id',
        'employee_id',
        string='Quản lý cửa hàng',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help='Các quản lý của cửa hàng.',
    )
    manager_id = fields.Many2one(
        'hr.employee',
        string='Quản lý cửa hàng (Chính)',
        compute='_compute_manager_id',
        inverse='_inverse_manager_id',
        store=True,
        ondelete='set null',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help='Quản lý chính (tương thích ngược).',
    )
    accountant_ids = fields.Many2many(
        'hr.employee',
        'hr_store_accountant_rel',
        'store_id',
        'employee_id',
        string='Kế toán',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help='Nhân viên kế toán phụ trách cửa hàng.',
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

    @api.depends('manager_ids')
    def _compute_manager_id(self):
        for store in self:
            store.manager_id = store.manager_ids[:1]

    def _inverse_manager_id(self):
        for store in self:
            if store.manager_id:
                if store.manager_id not in store.manager_ids:
                    store.manager_ids = [(4, store.manager_id.id)]
            else:
                store.manager_ids = [(5, 0, 0)]

    @api.depends('store_place_id', 'store_place_id.name')
    def _compute_store_place(self):
        for store in self:
            store.store_place = store.store_place_id.name or False

    def _inverse_store_place(self):
        for store in self:
            if store.store_place:
                place = self.env['hr.store.place'].sudo().search([
                    '|',
                    ('name', '=', store.store_place),
                    ('code', '=', store.store_place),
                ], limit=1)
                if not place:
                    place = self.env['hr.store.place'].sudo().create({
                        'name': store.store_place,
                        'code': store.store_place,
                    })
                store.store_place_id = place
            else:
                store.store_place_id = False

    def init(self):
        super().init()
        # Backfill store_place_id from legacy store_place string values if present
        self.env.cr.execute("""
            UPDATE hr_store s
            SET store_place_id = p.id
            FROM hr_store_place p
            WHERE s.store_place_id IS NULL
              AND s.store_place IS NOT NULL
              AND (s.store_place = p.name OR s.store_place = p.code)
        """)
        # Backfill hr_employee_managed_store_rel from legacy manager_id if present
        self.env.cr.execute("""
            INSERT INTO hr_employee_managed_store_rel (store_id, employee_id)
            SELECT s.id, s.manager_id
            FROM hr_store s
            WHERE s.manager_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM hr_employee_managed_store_rel rel
                  WHERE rel.store_id = s.id AND rel.employee_id = s.manager_id
              )
        """)

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
            # Fallback 1: If a related record (e.g. manager_ids or accountant_ids of another mien/dept)
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
                if f and f.type in ('many2one', 'many2many') and isinstance(fspec, dict) and 'fields' in fspec:
                    clean_spec[fname] = {}
            return super(HrStore, self.sudo()).web_read(clean_spec)
