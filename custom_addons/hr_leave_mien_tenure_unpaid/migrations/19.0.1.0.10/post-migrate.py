# -*- coding: utf-8 -*-
"""Grant current-month leave bonus to all newly eligible Bắc/Nam/ĐTT employees."""

import logging

from odoo import SUPERUSER_ID, api, fields

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Employee = env["hr.employee"].with_context(active_test=False)
    today = fields.Date.context_today(Employee)
    month_start = today.replace(day=1)
    eligible = Employee.search([("active", "=", True)]).filtered(
        lambda employee: employee._monthly_leave_bonus_eligible(today)
        and employee.last_monthly_leave_bonus_date != month_start
    )
    if not eligible:
        return
    eligible._apply_monthly_leave_bonus(month_start)
    _logger.info(
        "hr_leave_mien_tenure_unpaid: granted monthly leave bonus to %d employees",
        len(eligible),
    )
