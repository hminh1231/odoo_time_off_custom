# -*- coding: utf-8 -*-
"""Reverse already-granted current-month leave for early departures."""

import logging

from odoo import SUPERUSER_ID, api, fields

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Employee = env["hr.employee"].with_context(active_test=False)
    today = fields.Date.context_today(Employee)
    month_start = today.replace(day=1)
    cutoff_end = today.replace(day=19)
    employees = Employee.search(
        [
            ("ngay_nghi_viec", ">=", month_start),
            ("ngay_nghi_viec", "<=", cutoff_end),
            ("departure_monthly_leave_reversal_date", "!=", month_start),
        ]
    )
    if not employees:
        return

    employees.with_context(
        monthly_leave_bonus_date=month_start,
    )._reverse_departure_monthly_leave_bonus(month_start)
    _logger.info(
        "hr_leave_mien_tenure_unpaid: checked %d current-month early "
        "departures for monthly leave reversal",
        len(employees),
    )
