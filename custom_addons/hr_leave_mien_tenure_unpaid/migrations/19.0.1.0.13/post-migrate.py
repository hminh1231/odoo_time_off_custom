# -*- coding: utf-8 -*-
"""Backfill initial monthly leave bonus after sync hook improvements."""

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
    eligible._sync_initial_monthly_leave_bonus()
    _logger.info(
        "hr_leave_mien_tenure_unpaid: synced initial leave bonus for %d employees",
        len(eligible),
    )
