from odoo import api, fields, models, tools
from odoo.fields import Domain


class HrStoreCode(models.Model):
    _name = 'hr.store.code'
    _description = 'Mã cửa hàng'
    _rec_name = 'code'
    _auto = False
    _order = 'code'

    store_id = fields.Many2one('hr.store', string='Cửa hàng', readonly=True)
    code = fields.Char(string='Mã cửa hàng', readonly=True)
    name = fields.Char(string='Tên cửa hàng', readonly=True)
    mien = fields.Selection(
        selection=[
            ('Bắc', 'Bắc'),
            ('Nam', 'Nam'),
            ('ĐTT', 'ĐTT'),
            ('VP', 'VP'),
        ],
        string='Miền',
        readonly=True,
    )
    active = fields.Boolean(readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS
            SELECT
                id,
                id AS store_id,
                code,
                name,
                mien,
                active
            FROM hr_store
            WHERE code IS NOT NULL
              AND TRIM(code) != ''
        """)

    @api.model
    @api.readonly
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        # NOTE: the underlying SQL view exposes `name` from hr_store.name which is
        # a translatable (jsonb) column; an ILIKE on it raises
        # "operator does not exist: jsonb ~~*". The record is displayed by `code`,
        # so we only search on `code` here to keep the picker working.
        search_domain = Domain(domain or Domain.TRUE)
        if name:
            search_domain &= Domain('code', operator, name)
        records = self.search_fetch(search_domain, ['code'], limit=limit)
        return [(store.id, store.code or '') for store in records.sudo()]

    @api.model
    @api.readonly
    def web_name_search(self, name, specification, domain=None, operator='ilike', limit=100):
        id_name_pairs = self.name_search(name, domain, operator, limit)
        if len(specification) == 1 and 'display_name' in specification:
            return [
                {
                    'id': record_id,
                    'display_name': label,
                    '__formatted_display_name': label,
                }
                for record_id, label in id_name_pairs
            ]
        records = self.browse([record_id for record_id, _ in id_name_pairs])
        return records.web_read(specification)
