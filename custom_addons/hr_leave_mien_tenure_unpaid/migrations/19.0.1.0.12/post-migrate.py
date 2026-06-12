# -*- coding: utf-8 -*-
"""Backfill initial monthly leave bonus for eligible employees missed by prior rules."""

import logging

from odoo import SUPERUSER_ID, api, fields

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Employee = env["hr.employee"].with_context(active_test=False)
    today = fields.Date.context_today(Employee)
    eligible = Employee.search([("active", "=", True)]).filtered(
        lambda employee: employee._monthly_leave_bonus_eligible(today)
        and not employee.last_monthly_leave_bonus_date
    )
    if not eligible:
        return
    eligible._apply_monthly_leave_bonus(today.replace(day=1))
    _logger.info(
        "hr_leave_mien_tenure_unpaid: backfilled initial leave bonus for %d employees",
        len(eligible),
    )
