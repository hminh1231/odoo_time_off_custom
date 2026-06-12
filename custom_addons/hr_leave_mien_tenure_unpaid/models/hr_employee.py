# -*- coding: utf-8 -*-

from datetime import datetime, time, timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields, models
from odoo.tools import format_date
from odoo.tools.translate import _

# Miền áp dụng quy tắc (trùng Bắc / Nam / ĐTT trong hr_employee_hrm_detail).
MIEN_TENURE_UNPAID_CODES = frozenset({"Bắc", "Nam", "ĐTT"})
TENURE_YEARS_FOR_NORMAL_LEAVE = 4
# Quy tắc thâm niên/ngày lễ chỉ áp dụng cho chức danh «Nhóm trưởng».
TENURE_UNPAID_JOB_POSITION = "nhóm trưởng"


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _get_leave_mien_for_rules(self):
        self.ensure_one()
        if hasattr(self, "_get_leave_mien"):
            return self._get_leave_mien()
        if self.mien:
            return self.mien
        if self.ma_bo_phan_id:
            return self.ma_bo_phan_id.mien
        return False

    def _employee_job_position_key(self):
        """Normalized job label used for tenure / leave rules."""
        self.ensure_one()
        if "job_title" in self._fields and self.job_title:
            return str(self.job_title).strip().casefold()
        return (self.job_id.name or "").strip().casefold()

    def _is_tenure_unpaid_job_position(self):
        """Chức danh «Nhóm trưởng» — chỉ nhóm này mới áp quy tắc thâm niên/ngày lễ."""
        self.ensure_one()
        return self._employee_job_position_key() == TENURE_UNPAID_JOB_POSITION

    def _mien_monthly_leave_bonus_applies(self):
        """Miền Bắc / Nam / ĐTT — áp dụng cộng phép hàng tháng cho mọi chức danh."""
        self.ensure_one()
        return self._get_leave_mien_for_rules() in MIEN_TENURE_UNPAID_CODES

    def _mien_tenure_unpaid_applies(self):
        """Miền Bắc / Nam / ĐTT và chức danh «Nhóm trưởng»."""
        self.ensure_one()
        if not self._is_tenure_unpaid_job_position():
            return False
        return self._mien_monthly_leave_bonus_applies()

    def _mien_tenure_has_four_years(self, reference_date=None):
        """Đủ 4 năm làm việc tính từ Ngày vào làm tới ngày tham chiếu (mặc định: hôm nay)."""
        self.ensure_one()
        join_date = self.ngay_vao_lam
        if not join_date:
            return False
        ref = reference_date or fields.Date.today()
        return join_date + relativedelta(years=TENURE_YEARS_FOR_NORMAL_LEAVE) <= ref

    def _mien_tenure_unpaid_required(self, reference_date=None):
        """
        Bắt buộc mọi đơn nghỉ dùng loại (O) khi thuộc miền Bắc/Nam/ĐTT
        và chưa đủ 4 năm (hoặc thiếu Ngày vào làm).
        """
        self.ensure_one()
        if not self._mien_tenure_unpaid_applies():
            return False
        return not self._mien_tenure_has_four_years(reference_date=reference_date)

    def _mien_tenure_work_duration_label(self, reference_date=None):
        """Thâm niên làm việc từ Ngày vào làm (HRM) tới ngày tham chiếu."""
        self.ensure_one()
        join_date = self.ngay_vao_lam
        ref = reference_date or fields.Date.today()
        if not join_date:
            return _("chưa khai báo")
        if ref < join_date:
            return _("0 ngày")
        delta = relativedelta(ref, join_date)
        parts = []
        if delta.years:
            parts.append(_("%(years)s năm") % {"years": delta.years})
        if delta.months:
            parts.append(_("%(months)s tháng") % {"months": delta.months})
        if delta.days:
            parts.append(_("%(days)s ngày") % {"days": delta.days})
        return ", ".join(parts) if parts else _("0 ngày")

    def _mien_tenure_unpaid_notice_message(self, reference_date=None):
        self.ensure_one()
        if not self._mien_tenure_unpaid_required(reference_date=reference_date):
            return False
        join_date = self.ngay_vao_lam
        join_label = (
            format_date(self.env, join_date) if join_date else _("chưa khai báo")
        )
        duration = self._mien_tenure_work_duration_label(reference_date=reference_date)
        return _(
            "Đối với chức danh 'Nhóm trưởng', nếu thâm niên làm việc dưới 4 năm "
            "thì chỉ được tạo đơn nghỉ phép không lương (ngày vào làm của bạn là "
            "%(join)s, tổng thời gian bạn đã làm là %(duration)s)"
        ) % {"join": join_label, "duration": duration}

    @staticmethod
    def _coerce_leave_date(value):
        if not value:
            return False
        if isinstance(value, datetime):
            return value.date()
        return fields.Date.to_date(value)

    def _leave_range_overlaps_public_holiday(self, date_from, date_to):
        """Ít nhất một ngày trong khoảng nghỉ trùng Public Holiday của nhân viên."""
        self.ensure_one()
        date_from = self._coerce_leave_date(date_from)
        date_to = self._coerce_leave_date(date_to) or date_from
        if not date_from:
            return False
        if date_to < date_from:
            date_from, date_to = date_to, date_from
        dt_start = datetime.combine(date_from, time.min)
        dt_end = datetime.combine(date_to, time.max)
        public_holidays = self._get_public_holidays(dt_start, dt_end)
        if not public_holidays:
            return False
        current = date_from
        while current <= date_to:
            for ph in public_holidays:
                ph_start = fields.Datetime.to_datetime(ph.date_from).date()
                ph_end = fields.Datetime.to_datetime(ph.date_to).date()
                if ph_start <= current <= ph_end:
                    return True
            current += timedelta(days=1)
        return False

    def _mien_public_holiday_unpaid_required(self, date_from, date_to):
        """Bắt buộc (O) khi khoảng nghỉ có ngày trùng Public Holiday."""
        self.ensure_one()
        if not self._mien_tenure_unpaid_applies():
            return False
        return self._leave_range_overlaps_public_holiday(date_from, date_to)

    def _mien_unpaid_o_required(self, date_from=None, date_to=None):
        """Gộp quy tắc thâm niên (< 4 năm) và nghỉ trùng ngày lễ."""
        self.ensure_one()
        if not self._mien_tenure_unpaid_applies():
            return False
        if self._mien_tenure_unpaid_required():
            return True
        if date_from:
            return self._leave_range_overlaps_public_holiday(date_from, date_to)
        return False
