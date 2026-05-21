# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo import api, fields, models

VP_REGION_CODE = "VP"
MODE_BLOCK = "block"
MODE_EXCLUDE = "exclude"
ICP_MODE_KEY = "hr_leave_vp_sunday.mode"


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    @api.model
    def _vp_sunday_mode(self):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(ICP_MODE_KEY, MODE_BLOCK)
        )

    def _is_vp_region(self):
        self.ensure_one()
        return self.mien == VP_REGION_CODE

    @api.model
    def _mark_sundays_unusual(self, unusual_days, start_date, end_date):
        day = start_date
        while day <= end_date:
            if day.weekday() == 6:
                unusual_days[fields.Date.to_string(day)] = True
            day += timedelta(days=1)
        return unusual_days

    def _get_unusual_days(self, date_from, date_to=None):
        unusual_days = super()._get_unusual_days(date_from, date_to)
        if self._vp_sunday_mode() != MODE_BLOCK:
            return unusual_days
        vp_employees = self.filtered(lambda e: e._is_vp_region())
        if not vp_employees:
            return unusual_days
        date_from_date = datetime.strptime(date_from, "%Y-%m-%d %H:%M:%S").date()
        date_to_date = (
            datetime.strptime(date_to, "%Y-%m-%d %H:%M:%S").date()
            if date_to
            else date_from_date
        )
        return self._mark_sundays_unusual(unusual_days, date_from_date, date_to_date)

    def _vp_sunday_exclude_applies(self):
        self.ensure_one()
        return self._is_vp_region() and self._vp_sunday_mode() == MODE_EXCLUDE

    @staticmethod
    def _exclude_sundays_from_work_time(work_time_per_day):
        return [(day, hours) for day, hours in work_time_per_day if day.weekday() != 6]

    def _list_work_time_per_day(self, from_datetime, to_datetime, calendar=None, domain=None):
        result = super()._list_work_time_per_day(
            from_datetime, to_datetime, calendar=calendar, domain=domain
        )
        for employee in self.filtered(lambda e: e._vp_sunday_exclude_applies()):
            if employee.id in result:
                result[employee.id] = employee._exclude_sundays_from_work_time(
                    result[employee.id]
                )
        return result

    def _get_work_days_data_batch(
        self, from_datetime, to_datetime, compute_leaves=True, calendar=None, domain=None
    ):
        result = super()._get_work_days_data_batch(
            from_datetime,
            to_datetime,
            compute_leaves=compute_leaves,
            calendar=calendar,
            domain=domain,
        )
        for employee in self.filtered(lambda e: e._vp_sunday_exclude_applies()):
            work_time = employee._list_work_time_per_day(
                from_datetime,
                to_datetime,
                calendar=calendar,
                domain=domain,
            )
            work_days = work_time.get(employee.id, [])
            result[employee.id] = {
                "days": len(work_days),
                "hours": sum(hours for _day, hours in work_days),
            }
        return result
