# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

MIEN_SELECTION = [
    ("Bắc", "Bắc"),
    ("Nam", "Nam"),
    ("ĐTT", "ĐTT"),
    ("VP", "VP"),
]

# Miền bắt buộc loại P1 cho đơn nghỉ đầu tiên trong tháng (theo lịch).
FIRST_MONTH_LEAVE_P1_MIEN_CODES = frozenset({"Bắc", "Nam", "ĐTT"})
# Mã loại phép = ngoặc () đầu tiên trong tên hr.leave.type, vd. «Nghỉ phép (P1) - …».
P1_LEAVE_TYPE_CODE = "P1"
P2_LEAVE_TYPE_CODE = "P2"
O_LEAVE_TYPE_CODE = "O"
# Tối đa 3 ngày phép (P1/P2) trong một tháng; từ ngày thứ 4 → (O).
MAX_PAID_LEAVE_DAYS_PER_MONTH = 3


class HrLeaveMienConfig(models.Model):
    _name = "hr.leave.mien.config"
    _description = "Phân chia loại ngày nghỉ theo Miền"
    _order = "sequence, mien, id"
    _rec_name = "mien"

    sequence = fields.Integer(default=10)
    mien = fields.Selection(
        MIEN_SELECTION,
        string="Miền",
        required=True,
        index=True,
    )
    line_ids = fields.One2many(
        "hr.leave.mien.line",
        "config_id",
        string="Loại ngày nghỉ",
    )

    _mien_unique = models.Constraint(
        "unique (mien)",
        "Mỗi Miền chỉ được cấu hình một lần.",
    )

    @api.depends("mien", "line_ids.leave_type_id")
    def _compute_display_name(self):
        labels = dict(MIEN_SELECTION)
        for config in self:
            mien_label = labels.get(config.mien, config.mien or "")
            count = len(config.line_ids)
            config.display_name = f"{mien_label} ({count} loại)"

    @api.constrains("line_ids")
    def _check_leave_types_active(self):
        for config in self:
            archived = config.line_ids.leave_type_id.filtered(lambda lt: not lt.active)
            if archived:
                raise ValidationError(
                    _("Các loại ngày nghỉ sau đã được lưu trữ: %s")
                    % ", ".join(archived.mapped("name"))
                )

    @api.model
    def _get_config_for_mien(self, mien):
        if not mien:
            return self.browse()
        return self.search([("mien", "=", mien)], limit=1)

    @api.model
    def _get_leave_type_ids_for_mien(self, mien):
        config = self._get_config_for_mien(mien)
        return config.line_ids.leave_type_id.ids if config else []

    @api.model
    def _is_mien_configured(self, mien):
        return bool(self._get_leave_type_ids_for_mien(mien))
