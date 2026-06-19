# -*- coding: utf-8 -*-

from odoo import api, fields, models

LEGACY_MIEN_TO_ZONE_CODE = {
    "VP": "vp",
    "Nam": "ch_nam",
    "ĐTT": "ch_dtt",
    "Bắc": "ch_bac",
    "Tất cả": "all",
}


class HrMienZone(models.Model):
    _name = "hr.mien.zone"
    _description = "Khu vực miền (VP / CH)"
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = "name"
    _order = "parent_path, sequence, id"

    name = fields.Char(string="Tên miền", required=True, translate=True)
    code = fields.Char(string="Mã", required=True, index=True)
    parent_id = fields.Many2one("hr.mien.zone", string="Miền cha", ondelete="cascade", index=True)
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many("hr.mien.zone", "parent_id", string="Miền con")
    sequence = fields.Integer(default=10)
    legacy_mien = fields.Selection(
        selection=[
            ("Bắc", "Bắc"),
            ("Nam", "Nam"),
            ("ĐTT", "ĐTT"),
            ("VP", "VP"),
            ("Tất cả", "Tất cả"),
        ],
        string="Miền (dữ liệu)",
        help="Giá trị miền trên hồ sơ nhân viên tương ứng với khu vực này.",
    )
    is_assignable = fields.Boolean(
        string="Gán cho nhân viên",
        default=True,
        help="Chỉ các miền lá (VP, Miền Nam/ĐTT/Bắc, Tất cả) mới gán trực tiếp cho nhân viên.",
    )
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint(
        "unique(code)",
        "Mã khu vực miền phải là duy nhất.",
    )

    @api.model
    def zone_from_legacy_mien(self, mien):
        code = LEGACY_MIEN_TO_ZONE_CODE.get(mien)
        if not code:
            return self.env["hr.mien.zone"]
        return self.search([("code", "=", code)], limit=1)
