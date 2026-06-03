# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from io import BytesIO

import xlsxwriter

from odoo import _, api, fields, models
from odoo.exceptions import UserError

VP_FORM_HEADERS = [
    "MIỀN",
    "ID NHÂN VIÊN",
    "TÊN NHÂN VIÊN",
    "MÃ BỘ PHẬN",
    "CHỨC VỤ",
    "NGÀY NGHỈ",
    "SỐ NGÀY NGHỈ",
    "LÝ DO NGHỈ",
    "NGƯỜI NHẬN BÀN GIAO",
    "ĐƠN XIN NGHỈ PHÉP",
]
COL_VP_FORM_IMAGE = VP_FORM_HEADERS.index("ĐƠN XIN NGHỈ PHÉP")
VP_FORM_IMAGE_ROW_HEIGHT = 72


class HrLeaveMatrixExportWizard(models.TransientModel):
    _name = "hr.leave.matrix.export.wizard"
    _inherit = ["hr.leave.store.export.mixin"]
    _description = "Export VP time off form (Excel)"

    year = fields.Integer(required=True, default=lambda self: fields.Date.context_today(self).year)
    month = fields.Integer(
        required=True,
        default=lambda self: fields.Date.context_today(self).month,
        help="Calendar month for leave requests in the export.",
    )
    domain_json = fields.Text(
        string="Search domain (JSON)",
        help="Technical: current list filters from the Time Off list view.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.pop("export_kind", None)
        return super().create(vals_list)

    def write(self, vals):
        vals.pop("export_kind", None)
        return super().write(vals)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        raw = ctx.get("matrix_export_domain_json")
        if raw is not None and "domain_json" in fields_list:
            res["domain_json"] = raw if isinstance(raw, str) else json.dumps(raw)
        res.pop("export_kind", None)
        return res

    @api.constrains("month")
    def _check_month(self):
        for wiz in self:
            if wiz.month < 1 or wiz.month > 12:
                raise UserError(_("Month must be between 1 and 12."))

    def _parse_domain(self):
        self.ensure_one()
        raw = (self.domain_json or "").strip()
        if not raw:
            return []
        try:
            domain = json.loads(raw)
        except json.JSONDecodeError as e:
            raise UserError(_("Invalid search domain: %s") % e) from e
        if not isinstance(domain, list):
            raise UserError(_("Search domain must be a list."))
        return domain

    def _row_values_for_vp_form(self, leave):
        emp = leave.employee_id
        return [
            self._mien_label(emp) if emp else "",
            (getattr(emp, "id_hrm", None) or "").strip() if emp else "",
            (emp.name or "").upper() if emp else "",
            (getattr(emp, "ma_bo_phan", None) or "").strip().upper() if emp else "",
            self._job_title_label(emp),
            self._format_ngay_nghi_display(leave),
            self._format_so_ngay_nghi_label(leave),
            self._leave_reason(leave),
            self._handover_recipient_names(leave),
        ]

    def _write_vp_form_image(self, sheet, row, leave, cell_fmt):
        image_bytes = self._leave_form_image_bytes(leave)
        if not image_bytes:
            sheet.write(row, COL_VP_FORM_IMAGE, "", cell_fmt)
            return
        sheet.set_row(row, VP_FORM_IMAGE_ROW_HEIGHT)
        sheet.insert_image(
            row,
            COL_VP_FORM_IMAGE,
            "don_nghi.png",
            {
                "image_data": BytesIO(image_bytes),
                "x_offset": 4,
                "y_offset": 4,
                "x_scale": 0.3,
                "y_scale": 0.3,
                "object_position": 1,
            },
        )

    def action_export_matrix_excel(self):
        """FORM KẾT XUẤT NGHỈ PHÉP — miền VP (một đơn = một dòng)."""
        self.ensure_one()
        self._check_matrix_export_mien(self.MIEN_VP_CODES)

        year, month = int(self.year), int(self.month)
        leaves = self._search_leaves_in_mien(
            year, month, self._parse_domain(), self.MIEN_VP_CODES
        )

        buffer = BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})
        sheet = workbook.add_worksheet("Nghỉ phép VP")

        title_fmt = workbook.add_format(
            {"bold": True, "font_size": 12, "align": "center", "valign": "vcenter"}
        )
        header_fmt = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#BDD7EE",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            }
        )
        cell_fmt = workbook.add_format({"border": 1, "valign": "top", "text_wrap": True})

        sheet.merge_range(
            0, 0, 0, len(VP_FORM_HEADERS) - 1, "FORM KẾT XUẤT NGHỈ PHÉP", title_fmt
        )
        for col, title in enumerate(VP_FORM_HEADERS):
            sheet.write(1, col, title, header_fmt)
        sheet.set_row(1, 22)

        row = 2
        for leave in leaves:
            values = self._row_values_for_vp_form(leave)
            for col, value in enumerate(values):
                sheet.write(row, col, value, cell_fmt)
            self._write_vp_form_image(sheet, row, leave, cell_fmt)
            row += 1

        if row == 2:
            sheet.write_row(2, 0, [""] * len(VP_FORM_HEADERS), cell_fmt)
            row = 3

        sheet.freeze_panes(2, 0)
        sheet.set_column(0, 0, 10)
        sheet.set_column(1, 1, 14)
        sheet.set_column(2, 2, 30)
        sheet.set_column(3, 4, 14)
        sheet.set_column(5, 6, 18)
        sheet.set_column(7, 7, 36)
        sheet.set_column(8, 8, 40)
        sheet.set_column(COL_VP_FORM_IMAGE, COL_VP_FORM_IMAGE, 30)

        workbook.close()
        buffer.seek(0)
        filename = "form_ket_xuat_nghi_phep_vp_%s-%02d.xlsx" % (year, month)

        attachment = self.env["ir.attachment"].create(
            {
                "name": filename,
                "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "raw": buffer.read(),
                "res_model": self._name,
                "res_id": self.id,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % attachment.id,
            "target": "self",
        }
