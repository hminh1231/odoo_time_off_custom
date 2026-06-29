# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from odoo import api, fields, models

from .resource_calendar_leaves import (
    HOLIDAY_SCOPE_CH,
    HOLIDAY_SCOPE_VP,
    SKIP_HOLIDAY_SCOPE_SEARCH_CTX,
)

_STORE_MIENS = frozenset({"Bắc", "Nam", "ĐTT"})
_STORE_CALENDAR_XMLID = "hr_public_holiday_mien.resource_calendar_store_full_week"


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _employee_schedule_mien(self):
        self.ensure_one()
        emp = self.sudo()
        mien = (emp.mien or "").strip()
        if not mien and emp.mien_zone_id:
            mien = (emp.mien_zone_id.legacy_mien or "").strip()
        if not mien and emp.ma_bo_phan_id:
            mien = (emp.ma_bo_phan_id.mien or "").strip()
        return mien

    def _uses_store_full_week_schedule(self):
        self.ensure_one()
        return self._employee_schedule_mien() in _STORE_MIENS

    def _public_holiday_scope_for_employee(self):
        self.ensure_one()
        mien = self._employee_schedule_mien()
        if mien == "VP":
            return HOLIDAY_SCOPE_VP
        if mien in _STORE_MIENS:
            return HOLIDAY_SCOPE_CH
        return False

    @api.model
    def _public_holiday_scope_for_current_user(self):
        employee = self.env.user.employee_id
        if not employee:
            return False
        return employee._public_holiday_scope_for_employee()

    def _public_holiday_search_env(self):
        """Calendar leaves env without per-user scope filter (scope applied below)."""
        return self.env["resource.calendar.leaves"].with_context(
            **{SKIP_HOLIDAY_SCOPE_SEARCH_CTX: True}
        ).sudo()

    def _public_holiday_base_domain(self, date_start, date_end):
        self.ensure_one()
        return [
            ("resource_id", "=", False),
            ("company_id", "in", self.env.companies.ids),
            ("date_from", "<=", date_end),
            ("date_to", ">=", date_start),
            "|",
            ("calendar_id", "=", False),
            ("calendar_id", "=", self.resource_calendar_id.id),
        ]

    def _filter_public_holidays_by_mien(self, holidays):
        """Time-off calendar shows national VP holidays for every Miền.

        CH-scoped rows are configured separately (Cửa Hàng tab) and are not
        mixed into the employee calendar sidebar.
        """
        self.ensure_one()
        return holidays.filtered(lambda leave: leave.holiday_scope == HOLIDAY_SCOPE_VP)

    def _get_public_holidays(self, date_start, date_end):
        """Return public holidays for sidebar / overlap rules, scoped by Miền.

        Store staff keep the 7-day working calendar (no holiday deduction in leave
        duration); this method only controls which holidays are shown on the time-off
        calendar and used by tenure/overlap checks.
        """
        self.ensure_one()
        holidays = self._public_holiday_search_env().search(
            self._public_holiday_base_domain(date_start, date_end)
        )
        return self._filter_public_holidays_by_mien(holidays)

    def _parse_unusual_day_range(self, date_from, date_to=None):
        if isinstance(date_from, str):
            date_from = datetime.strptime(date_from, "%Y-%m-%d %H:%M:%S")
        if date_to is None:
            date_to = date_from
        elif isinstance(date_to, str):
            date_to = datetime.strptime(date_to, "%Y-%m-%d %H:%M:%S")
        return date_from, date_to

    def _get_unusual_days(self, date_from, date_to=None):
        unusual_days = super()._get_unusual_days(date_from, date_to)
        self.ensure_one()
        range_start, range_end = self._parse_unusual_day_range(date_from, date_to)
        holidays = self._get_public_holidays(range_start, range_end)
        for holiday in holidays:
            ph_start = fields.Datetime.to_datetime(holiday.date_from).date()
            ph_end = fields.Datetime.to_datetime(holiday.date_to).date()
            current = ph_start
            while current <= ph_end:
                unusual_days[fields.Date.to_string(current)] = True
                current += timedelta(days=1)
        return unusual_days

    def _recompute_open_leaves_calendar(self):
        if not self:
            return
        leaves = self.env["hr.leave"].search(
            [
                ("employee_id", "in", self.ids),
                ("state", "in", ["draft", "confirm", "validate1"]),
            ]
        )
        if not leaves:
            return
        fields_to_recompute = ("resource_calendar_id", "number_of_days", "number_of_hours")
        for field_name in fields_to_recompute:
            self.env.add_to_compute(leaves._fields[field_name], leaves)
        leaves._recompute_recordset(list(fields_to_recompute))

    def _sync_store_working_calendar(self):
        store_calendar = self.env.ref(_STORE_CALENDAR_XMLID, raise_if_not_found=False)
        if not store_calendar:
            return
        store_employees = self.env["hr.employee"]
        for employee in self:
            if not employee._uses_store_full_week_schedule():
                continue
            version = employee.version_id
            if version and version.resource_calendar_id != store_calendar:
                version.resource_calendar_id = store_calendar
            store_employees |= employee
        store_employees._recompute_open_leaves_calendar()

    @api.model
    def _upgrade_sync_store_working_calendars(self):
        self.search([])._sync_store_working_calendar()

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees._sync_store_working_calendar()
        return employees

    def write(self, vals):
        res = super().write(vals)
        if {"mien", "mien_zone_id", "ma_bo_phan_id"} & set(vals):
            self._sync_store_working_calendar()
        return res
