# -*- coding: utf-8 -*-

from odoo import api, models

from .resource_calendar_leaves import HOLIDAY_SCOPE_CH, HOLIDAY_SCOPE_VP

_STORE_MIENS = frozenset({"Bắc", "Nam", "ĐTT"})


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _public_holiday_scope_for_employee(self):
        self.ensure_one()
        mien = (self.mien or "").strip()
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

    def _get_public_holidays(self, date_start, date_end):
        holidays = super()._get_public_holidays(date_start, date_end)
        scope = self._public_holiday_scope_for_employee()
        if scope:
            holidays = holidays.filtered(lambda leave: leave.holiday_scope == scope)
        return holidays
