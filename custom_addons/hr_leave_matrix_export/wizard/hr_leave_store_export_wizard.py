# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import calendar
import json
import re
from datetime import date, datetime, time, timedelta
from io import BytesIO

import xlsxwriter

from odoo import _, api, fields, models
from odoo.exceptions import UserError

STORE_HEADERS = [
    "MIỀN",
    "ID NHÂN VIÊN",
    "TÊN NHÂN VIÊN",
    "MÃ BỘ PHẬN",
    "CHỨC VỤ",
    "Ngày tạo đơn",
    "NGÀY NGHỈ Bắt đầu",
    "Ngày nghỉ kết thúc",
    "SỐ NGÀY NGHỈ",
    "LÝ DO NGHỈ",
    "NGƯỜI NHẬN BÀN GIAO",
    "ASM DUYỆT",
    "NGÀY ASM DUYỆT",
    "AD DUYỆT",
    "NGÀY AD DUYỆT",
    "trạng thái",
    "ký hiệu",
]

MIEN_DISPLAY = {
    "Bắc": "BẮC",
    "Nam": "NAM",
    "ĐTT": "ĐTT",
    "VP": "VP",
}

JOB_TITLE_SHORT = {
    "cửa hàng trưởng": "CHT",
    "asm": "ASM",
    "rsm": "RSM",
    "nhân viên ch": "NVCH",
    "nhân viên vp": "NVVP",
    "trưởng nhóm": "TN",
    "giám sát": "GS",
    "admin": "AD",
    "admin tổng": "AD",
}

# Khớp time_off_extra_approval._DEFAULT_LEAD_DAYS (giám đốc miễn rule nhưng vẫn có ngưỡng 7 ngày)
_DEFAULT_EMERGENCY_LEAD_DAYS = 7

IMPORT_CAPNHATCONG_HEADERS = [
    "Stt",
    "Ngay_Ct",
    "Ma_Bp",
    "Is_UuTien",
    "Update_Type",
    "Ghi_Chu",
    "Ma_Khieu",
    "Ma_CbNv",
    "Ngay_Bd",
    "Ngay_Kt",
    "Tong_Gio",
    "MA_LOI_CC",
]

# Giá trị mặc định — có thể chỉnh sau (theo file mẫu import cập nhật công CH)
IMPORT_CAPNHATCONG_DEFAULT_MA_BP = "LUG_IPH"
IMPORT_CAPNHATCONG_DEFAULT_IS_UUTIEN = 1
IMPORT_CAPNHATCONG_DEFAULT_UPDATE_TYPE = "1-Cập nhật công"
IMPORT_CAPNHATCONG_DEFAULT_GHI_CHU = ""

# Tong_Gio mặc định theo Ma_Khieu (giờ)
TONG_GIO_P1 = 10
TONG_GIO_P2_PER_DAY = 8
TONG_GIO_O = 0

IMPORT_CAPNHATCONG_COL_MA_KHIEU = IMPORT_CAPNHATCONG_HEADERS.index("Ma_Khieu")
IMPORT_CAPNHATCONG_COL_TONG_GIO = IMPORT_CAPNHATCONG_HEADERS.index("Tong_Gio")


class HrLeaveStoreExportMixin(models.AbstractModel):
    """Store form Excel export (used via hr.leave.matrix.export.wizard)."""

    _name = "hr.leave.store.export.mixin"
    _description = "Export store time off (FORM KẾT XUẤT NGHỈ PHÉP)"

    # Kết xuất CH: Bắc / Nam / ĐTT — Kết xuất VP (ma trận): VP
    MIEN_CH_CODES = frozenset({"Bắc", "Nam", "ĐTT"})
    MIEN_VP_CODES = frozenset({"VP"})

    @staticmethod
    def _format_date(value):
        if not value:
            return ""
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            return f"{value.day}/{value.month}/{value.year}"
        return str(value)

    @staticmethod
    def _leave_span_in_month(leave, month_start, month_end):
        """Khoảng nghỉ của đơn (cắt theo tháng xuất), tách mỗi ngày = một dòng."""
        if not leave.request_date_from or not leave.request_date_to:
            return None
        span_start = max(leave.request_date_from, month_start)
        span_end = min(leave.request_date_to, month_end)
        if span_start > span_end:
            return None
        return span_start, span_end

    @staticmethod
    def _iter_days(ngay_bd, ngay_kt):
        day = ngay_bd
        while day <= ngay_kt:
            yield day
            day += timedelta(days=1)

    def _employee_ma_cb_nv(self, employee):
        if not employee:
            return ""
        for attr in ("ma_cham_cong", "ma_nv_ke_toan", "id_hrm"):
            value = (getattr(employee, attr, None) or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _capnhatcong_day_count(ngay_bd, ngay_kt):
        if not ngay_bd or not ngay_kt:
            return 0
        return (ngay_kt - ngay_bd).days + 1

    @classmethod
    def _tong_gio_capnhatcong(cls, ma_khieu, ngay_bd, ngay_kt):
        code = (ma_khieu or "").strip().upper()
        days = cls._capnhatcong_day_count(ngay_bd, ngay_kt)
        if code == "P1":
            return TONG_GIO_P1
        if code == "P2":
            return TONG_GIO_P2_PER_DAY * days
        if code == "O":
            return TONG_GIO_O
        return ""

    def _import_capnhatcong_row_payload(self, leave, ngay_bd, ngay_kt, ma_khieu=None):
        employee = leave.employee_id
        ma_bp = (getattr(employee, "ma_bo_phan", None) or "").strip() if employee else ""
        if not ma_bp:
            ma_bp = IMPORT_CAPNHATCONG_DEFAULT_MA_BP
        if ma_khieu is None:
            ma_khieu = self._leave_type_symbol(leave)
        ghi_chu = (leave.notes or leave.private_name or leave.name or "").strip()
        return {
            "ma_bp": ma_bp,
            "ma_khieu": ma_khieu,
            "ma_cb": self._employee_ma_cb_nv(employee),
            "ngay_bd": ngay_bd,
            "ngay_kt": ngay_kt,
            "tong_gio": self._tong_gio_capnhatcong(ma_khieu, ngay_bd, ngay_kt),
            "ghi_chu": ghi_chu,
        }

    def _import_capnhatcong_row_values(self, stt, payload):
        return [
            stt,
            "",
            payload["ma_bp"],
            IMPORT_CAPNHATCONG_DEFAULT_IS_UUTIEN,
            IMPORT_CAPNHATCONG_DEFAULT_UPDATE_TYPE,
            payload.get("ghi_chu") or IMPORT_CAPNHATCONG_DEFAULT_GHI_CHU,
            self._ma_khieu_export_display(payload["ma_khieu"]),
            payload["ma_cb"],
            payload["ngay_bd"],
            payload["ngay_kt"],
            payload["tong_gio"],
            "",
        ]

    def _employee_mien(self, employee):
        """Miền nhân viên (trực tiếp hoặc từ mã bộ phận)."""
        if not employee:
            return None
        if hasattr(employee, "_get_leave_mien"):
            return employee._get_leave_mien()
        mien = getattr(employee, "mien", None)
        if mien:
            return mien
        dept = getattr(employee, "ma_bo_phan_id", None)
        if dept and getattr(dept, "mien", None):
            return dept.mien
        return None

    def _get_current_user_leave_mien(self):
        return self._employee_mien(self.env.user.employee_id)

    @api.model
    def _get_matrix_export_menu_access(self):
        """Menu kết xuất theo miền user (cần quyền export)."""
        if not self.env.user.has_group("base.group_allow_export"):
            return {"show_vp": False, "show_ch": False}
        mien = self._get_current_user_leave_mien()
        return {
            "show_vp": mien in self.MIEN_VP_CODES,
            "show_ch": mien in self.MIEN_CH_CODES,
        }

    def _check_matrix_export_mien(self, allowed_miens):
        if not self.env.user.has_group("base.group_allow_export"):
            raise UserError(_("You need export permissions to download this file."))
        mien = self._get_current_user_leave_mien()
        if mien not in allowed_miens:
            raise UserError(
                _("Bạn không có quyền kết xuất file này. Miền của bạn không khớp với loại kết xuất được chọn.")
            )

    def _leave_in_mien(self, leave, allowed_miens):
        return self._employee_mien(leave.employee_id) in allowed_miens

    def _mien_label(self, employee):
        mien = getattr(employee, "mien", None) or ""
        return MIEN_DISPLAY.get(mien, (mien or "").upper())

    def _job_title_code(self, employee):
        """Mã chức vụ ngắn (CHT, ASM…) — dùng nội bộ, không phải cột export."""
        if not employee:
            return ""
        ma = (getattr(employee, "ma_chuc_vu", None) or "").strip()
        if ma:
            return ma.upper()
        jt = employee.job_title or ""
        if jt in JOB_TITLE_SHORT:
            return JOB_TITLE_SHORT[jt]
        if "job_title" in employee._fields and employee._fields["job_title"].type == "selection":
            labels = dict(employee._fields["job_title"]._description_selection(self.env))
            label = labels.get(jt, jt)
            return (label or "").upper()
        return jt.upper()

    def _job_title_label(self, employee):
        """Chức danh hiển thị trên form export (vd. Giám đốc, Nhân viên CH)."""
        if not employee:
            return ""
        jt = employee.job_title or ""
        if jt and "job_title" in employee._fields:
            field = employee._fields["job_title"]
            if field.type == "selection":
                labels = dict(field._description_selection(self.env))
                if jt in labels and labels[jt]:
                    return labels[jt]
        if jt:
            return jt
        if employee.job_id:
            return (employee.job_id.name or "").strip()
        return ""

    def _handover_recipient_names(self, leave):
        if "handover_acceptance_ids" not in leave._fields:
            return ""
        lines = leave.handover_acceptance_ids
        if not lines:
            return ""
        names = lines.mapped("employee_id.name")
        return ", ".join(n for n in names if n)

    def _approval_for_job_title(self, leave, job_title_keys):
        """Return (approver display name, approval date str) from responsible approval lines."""
        if isinstance(job_title_keys, str):
            job_title_keys = (job_title_keys,)
        if "responsible_approval_line_ids" not in leave._fields:
            return "", ""
        lines = leave.responsible_approval_line_ids.sorted("sequence")

        def _matches(line):
            emp = line.user_id.employee_id
            return emp and (emp.job_title or "") in job_title_keys

        approved = lines.filtered(lambda line: line.state == "approved" and _matches(line))
        if approved:
            line = approved[0]
            emp = line.user_id.employee_id
            name = (emp.name or line.user_id.name or "").upper()
            return name, self._format_date(line.action_date)
        pending = lines.filtered(lambda line: line.state == "pending" and _matches(line))
        if pending:
            line = pending[0]
            emp = line.user_id.employee_id
            return (emp.name or line.user_id.name or "").upper(), ""
        return "", ""

    def _leave_emergency_reference_date(self, leave):
        """Ngày đối chiếu báo trước (lần tạo / cập nhật đơn gần nhất)."""
        days = []
        if leave.create_date:
            days.append(fields.Date.to_date(leave.create_date))
        if leave.write_date:
            days.append(fields.Date.to_date(leave.write_date))
        return max(days) if days else fields.Date.context_today(self)

    def _is_emergency_leave_for_export(self, leave):
        """Khớp logic UI (kể cả giám đốc: báo trước < 7 ngày vẫn là khẩn cấp)."""
        if getattr(leave, "is_emergency_leave", False):
            return True
        hr_leave = self.env["hr.leave"]
        if hasattr(hr_leave, "_needs_emergency_leave_confirmation"):
            return hr_leave._needs_emergency_leave_confirmation(
                res_id=leave.id,
                vals={
                    "employee_id": leave.employee_id.id,
                    "request_date_from": leave.request_date_from,
                    "request_date_to": leave.request_date_to,
                    "holiday_status_id": leave.holiday_status_id.id,
                },
            )
        if not hasattr(leave, "_required_lead_days_for_job_title"):
            return False
        employee = leave.employee_id
        start = leave.request_date_from
        if not employee or not start:
            return False
        ref_day = self._leave_emergency_reference_date(leave)
        delta = (start - ref_day).days
        required = leave._required_lead_days_for_job_title(employee.job_title)
        if required is not None:
            return delta < required
        return delta < _DEFAULT_EMERGENCY_LEAD_DAYS

    def _status_text(self, leave):
        """Bình thường vs khẩn cấp (theo quy định báo trước, không phải trạng thái duyệt)."""
        if self._is_emergency_leave_for_export(leave):
            return "khẩn cấp"
        return "bình thường"

    @staticmethod
    def _normalize_leave_type_code(raw):
        """P1, P2, O — không có dấu ngoặc."""
        code = (raw or "").strip()
        code = code.replace("（", "(").replace("）", ")")
        if code.startswith("(") and code.endswith(")"):
            code = code[1:-1].strip()
        return code

    @staticmethod
    def _ma_khieu_from_kind(kind):
        return {"p1": "P1", "p2": "P2", "o": "O"}.get((kind or "").lower(), "")

    def _iter_export_root_leaves(self, leaves):
        """Mỗi nhóm split_group_id chỉ xuất một lần (tránh trùng dòng)."""
        seen_groups = set()
        roots = self.env["hr.leave"]
        for leave in leaves.sorted(key=lambda lv: (lv.request_date_from or date.min, lv.id)):
            gid = getattr(leave, "split_group_id", None)
            if gid:
                if gid in seen_groups:
                    continue
                seen_groups.add(gid)
            roots |= leave
        return roots

    def _iter_leave_export_segments(self, leave, month_start=None, month_end=None):
        """Các đoạn P1/P2/O — khớp thông báo phân tích (DB tách hoặc kế hoạch tháng)."""
        self.ensure_one()

        def _clip(seg_from, seg_to):
            if not month_start or not month_end:
                return seg_from, seg_to
            start = max(seg_from, month_start)
            end = min(seg_to, month_end)
            if start > end:
                return None
            return start, end

        def _yield_segment(seg_leave, seg_from, seg_to, ma_khieu):
            clipped = _clip(seg_from, seg_to)
            if not clipped:
                return
            start, end = clipped
            yield {
                "leave": seg_leave,
                "ngay_bd": start,
                "ngay_kt": end,
                "ma_khieu": ma_khieu or self._leave_type_symbol(seg_leave),
            }

        if (
            getattr(leave, "split_group_id", None)
            and hasattr(leave, "_split_group_is_multi_segment")
            and leave._split_group_is_multi_segment()
        ):
            group = leave._get_split_group_leaves_all().sorted("request_date_from")
            for seg_leave in group:
                if not seg_leave.request_date_from or not seg_leave.request_date_to:
                    continue
                yield from _yield_segment(
                    seg_leave,
                    seg_leave.request_date_from,
                    seg_leave.request_date_to,
                    self._leave_type_symbol(seg_leave),
                )
            return

        if hasattr(leave, "_monthly_mien_split_plan") and hasattr(leave, "_monthly_p1p2_mien_applies"):
            if (
                leave.employee_id
                and leave.request_date_from
                and leave.request_date_to
                and leave._monthly_p1p2_mien_applies(leave.employee_id)
            ):
                exclude = [leave.id] if leave.id else []
                plan = leave._monthly_mien_split_plan(
                    leave.employee_id,
                    leave.request_date_from,
                    leave.request_date_to,
                    exclude,
                )
                if len(plan) > 1:
                    for kind, seg_from, seg_to in plan:
                        yield from _yield_segment(
                            leave, seg_from, seg_to, self._ma_khieu_from_kind(kind)
                        )
                    return

        if leave.request_date_from and leave.request_date_to:
            yield from _yield_segment(
                leave,
                leave.request_date_from,
                leave.request_date_to,
                self._leave_type_symbol(leave),
            )

    def _iter_leave_export_segments_merged(self, leave, month_start=None, month_end=None):
        """Gộp các đoạn liền kề cùng ký hiệu (P1/P2/O) thành một dòng.

        Đơn được lưu thành nhiều bản ghi 1 ngày (P1, P2, P2, O); với export ta gộp
        các ngày liên tiếp cùng ký hiệu lại: P1 → 1 dòng, P2 (vd 9–10/6) → 1 dòng,
        O → 1 dòng. Số ngày và khoảng ngày của dòng được tính lại theo đoạn gộp.
        """
        self.ensure_one()
        segments = list(
            self._iter_leave_export_segments(leave, month_start, month_end)
        )
        if not segments:
            return
        segments.sort(key=lambda seg: (seg["ngay_bd"], seg["ngay_kt"]))
        merged = []
        for seg in segments:
            if merged:
                prev = merged[-1]
                same_code = (
                    self._normalize_leave_type_code(prev["ma_khieu"]).upper()
                    == self._normalize_leave_type_code(seg["ma_khieu"]).upper()
                )
                contiguous = seg["ngay_bd"] == prev["ngay_kt"] + timedelta(days=1)
                if same_code and contiguous:
                    prev["ngay_kt"] = seg["ngay_kt"]
                    continue
            merged.append(dict(seg))
        yield from merged

    @classmethod
    def _ma_khieu_export_display(cls, ma_khieu):
        """Cột Ma_Khieu: không hiển thị O (payload vẫn giữ O để merge / Tong_Gio)."""
        code = cls._normalize_leave_type_code(ma_khieu)
        if code.upper() == "O":
            return ""
        return ma_khieu or ""

    def _leave_type_symbol(self, leave):
        """Mã loại nghỉ, vd. Nghỉ Phép (P1) -> P1."""
        leave_type = leave.holiday_status_id
        if not leave_type:
            return ""
        leave_type_model = self.env["hr.leave.type"]
        if hasattr(leave_type_model, "code_from_name"):
            code = leave_type_model.code_from_name(leave_type.name)
            if code:
                return self._normalize_leave_type_code(code)
        name = (leave_type.name or "").strip().replace("（", "(").replace("）", ")")
        if not name:
            return ""
        match = re.search(r"\(([^)]+)\)", name)
        if match:
            return self._normalize_leave_type_code(match.group(1))
        return self._normalize_leave_type_code(name)

    def _leave_reason(self, leave):
        return (leave.notes or leave.private_name or leave.name or "").strip()

    def _format_ngay_nghi_display(self, leave):
        """Một cột NGÀY NGHỈ: một ngày hoặc khoảng from–to."""
        d_from = self._format_date(leave.request_date_from)
        d_to = self._format_date(leave.request_date_to)
        if d_to and d_to != d_from:
            return f"{d_from} - {d_to}"
        return d_from

    @staticmethod
    def _format_so_ngay_nghi_label(leave):
        days = leave.number_of_days
        if not days:
            return ""
        count = int(days) if float(days).is_integer() else days
        return f"{count} NGÀY"

    def _leave_form_image_bytes(self, leave):
        """Ảnh đính kèm đơn nghỉ (cột ĐƠN XIN NGHỈ PHÉP)."""
        attachments = leave.attachment_ids
        if not attachments:
            attachments = self.env["ir.attachment"].sudo().search(
                [("res_model", "=", "hr.leave"), ("res_id", "=", leave.id)],
                order="id",
            )
        for att in attachments:
            mimetype = (att.mimetype or "").lower()
            if not mimetype.startswith("image/"):
                continue
            data = att.raw
            if not data and att.datas:
                data = base64.b64decode(att.datas)
            if data:
                return data
        return None

    def _search_leaves_in_mien(self, year, month, base_domain, mien_codes):
        last_day = calendar.monthrange(year, month)[1]
        month_start = date(year, month, 1)
        month_end = date(year, month, last_day)
        overlap = [
            ("request_date_from", "<=", month_end),
            ("request_date_to", ">=", month_start),
        ]
        domain = base_domain + overlap if base_domain else overlap
        leaves = self.env["hr.leave"].search(
            domain,
            order="employee_id, request_date_from, id",
        )
        return leaves.filtered(lambda leave: self._leave_in_mien(leave, mien_codes))

    def _row_for_leave_segment(self, segment):
        leave = segment["leave"]
        emp = leave.employee_id
        seg_from = segment["ngay_bd"]
        seg_to = segment["ngay_kt"]
        segment_days = (seg_to - seg_from).days + 1 if seg_from and seg_to else ""
        asm_name, asm_date = self._approval_for_job_title(leave, ("asm",))
        ad_name, ad_date = self._approval_for_job_title(leave, ("admin tổng", "admin"))
        return [
            self._mien_label(emp) if emp else "",
            (getattr(emp, "id_hrm", None) or "").strip() if emp else "",
            (emp.name or "").upper() if emp else "",
            (getattr(emp, "ma_bo_phan", None) or "").strip().upper() if emp else "",
            self._job_title_label(emp),
            self._format_date(leave.create_date),
            self._format_date(seg_from),
            self._format_date(seg_to),
            segment_days,
            self._leave_reason(leave),
            self._handover_recipient_names(leave),
            asm_name,
            asm_date,
            ad_name,
            ad_date,
            self._status_text(leave),
            segment["ma_khieu"],
        ]

    def _search_store_leaves(self, year, month, base_domain):
        last_day = calendar.monthrange(year, month)[1]
        month_start = date(year, month, 1)
        month_end = date(year, month, last_day)
        overlap = [
            ("request_date_from", "<=", month_end),
            ("request_date_to", ">=", month_start),
        ]
        domain = base_domain + overlap if base_domain else overlap
        leaves = self.env["hr.leave"].search(
            domain,
            order="employee_id, request_date_from, id",
        )
        return leaves.filtered(lambda leave: self._leave_in_mien(leave, self.MIEN_CH_CODES))

    def action_export_store_excel(self):
        self.ensure_one()
        self._check_matrix_export_mien(self.MIEN_CH_CODES)

        year, month = int(self.year), int(self.month)
        last_day = calendar.monthrange(year, month)[1]
        month_start = date(year, month, 1)
        month_end = date(year, month, last_day)
        leaves = self._search_store_leaves(year, month, self._parse_domain())

        buffer = BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})
        sheet = workbook.add_worksheet("Nghỉ phép CH")

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

        sheet.merge_range(0, 0, 0, len(STORE_HEADERS) - 1, "FORM KẾT XUẤT NGHỈ PHÉP", title_fmt)
        for col, title in enumerate(STORE_HEADERS):
            sheet.write(1, col, title, header_fmt)
        sheet.set_row(1, 22)

        row = 2
        for leave in self._iter_export_root_leaves(leaves):
            for segment in self._iter_leave_export_segments_merged(leave, month_start, month_end):
                values = self._row_for_leave_segment(segment)
                for col, value in enumerate(values):
                    sheet.write(row, col, value, cell_fmt)
                row += 1

        if row == 2:
            sheet.write_row(2, 0, [""] * len(STORE_HEADERS), cell_fmt)
            row = 3

        sheet.freeze_panes(2, 0)
        sheet.set_column(0, 0, 8)
        sheet.set_column(1, 1, 12)
        sheet.set_column(2, 2, 28)
        sheet.set_column(3, 4, 12)
        sheet.set_column(5, 8, 14)
        sheet.set_column(9, 9, 36)
        sheet.set_column(10, 10, 40)
        sheet.set_column(11, 14, 18)
        sheet.set_column(15, 15, 14)
        sheet.set_column(16, 16, 10)

        workbook.close()
        buffer.seek(0)
        filename = "form_ket_xuat_nghi_phep_ch_%s-%02d.xlsx" % (year, month)

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

    @staticmethod
    def _import_capnhatcong_xlwt_styles(xlwt_module):
        """Định dạng ô cho file .xls (Excel 97–2003) — phần mềm công thường yêu cầu."""
        borders = "borders: left thin, right thin, top thin, bottom thin"
        header = xlwt_module.easyxf(
            "font: bold on; align: horiz center, vert center; "
            f"pattern: pattern solid, fore_colour pale_blue; {borders}"
        )
        cell = xlwt_module.easyxf(borders)
        red = xlwt_module.easyxf(f"font: colour red; {borders}")
        red_int = xlwt_module.easyxf(f"font: colour red; {borders}", num_format_str="0")
        date_cell = xlwt_module.easyxf(borders, num_format_str="M/D/YY")
        return header, cell, red, red_int, date_cell

    def _build_import_capnhatcong_xls(self, payloads):
        try:
            import xlwt  # noqa: PLC0415
        except ImportError as err:
            raise UserError(
                _("Thư viện Python xlwt chưa cài. Chạy: pip install xlwt")
            ) from err

        header_style, cell_style, red_style, red_int_style, date_style = (
            self._import_capnhatcong_xlwt_styles(xlwt)
        )
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet("import_capnhatcong CUA HANG"[:31])

        for col, title in enumerate(IMPORT_CAPNHATCONG_HEADERS):
            sheet.write(0, col, title, header_style)

        row = 1
        for stt, payload in enumerate(payloads, start=1):
            values = self._import_capnhatcong_row_values(stt, payload)
            tong_gio = payload["tong_gio"]
            for col, value in enumerate(values):
                if col in (8, 9) and isinstance(value, date):
                    sheet.write(
                        row,
                        col,
                        datetime.combine(value, time.min),
                        date_style,
                    )
                elif col == IMPORT_CAPNHATCONG_COL_MA_KHIEU:
                    sheet.write(
                        row,
                        col,
                        self._ma_khieu_export_display(payload["ma_khieu"]),
                        red_style,
                    )
                elif col == IMPORT_CAPNHATCONG_COL_TONG_GIO:
                    if tong_gio == "":
                        sheet.write(row, col, "", red_style)
                    else:
                        sheet.write(row, col, int(tong_gio), red_int_style)
                else:
                    sheet.write(row, col, value if value != "" else "", cell_style)
            row += 1

        if row == 1:
            for col in range(len(IMPORT_CAPNHATCONG_HEADERS)):
                sheet.write(1, col, "", cell_style)

        buffer = BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    def action_export_import_capnhatcong_ch_excel(self):
        """File import cập nhật công cửa hàng (miền Bắc / Nam / ĐTT) — định dạng .xls."""
        self.ensure_one()
        self._check_matrix_export_mien(self.MIEN_CH_CODES)

        year, month = int(self.year), int(self.month)
        last_day = calendar.monthrange(year, month)[1]
        month_start = date(year, month, 1)
        month_end = date(year, month, last_day)
        leaves = self._search_store_leaves(year, month, self._parse_domain())

        payloads = []
        for leave in self._iter_export_root_leaves(leaves):
            for segment in self._iter_leave_export_segments_merged(leave, month_start, month_end):
                payloads.append(
                    self._import_capnhatcong_row_payload(
                        segment["leave"],
                        segment["ngay_bd"],
                        segment["ngay_kt"],
                        ma_khieu=segment["ma_khieu"],
                    )
                )

        data = self._build_import_capnhatcong_xls(payloads)
        filename = "import_capnhatcong CUA HANG_%s-%02d.xls" % (year, month)

        attachment = self.env["ir.attachment"].create(
            {
                "name": filename,
                "mimetype": "application/vnd.ms-excel",
                "raw": data,
                "res_model": self._name,
                "res_id": self.id,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % attachment.id,
            "target": "self",
        }
