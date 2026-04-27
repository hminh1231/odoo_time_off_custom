# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Refresh conditional read domains (Employees=No must override implied hr.group_hr_user)."""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

DOMAIN = (
    "['|', ('user_id', '=', user.id), ('id', '=', user.employee_id.id)] "
    "if user.has_group('hr_employee_self_only.group_hr_employees_no') "
    "else [(1, '=', 1)] if user.has_group('hr.group_hr_manager') or user.has_group('hr.group_hr_user') "
    "else ['|', ('user_id', '=', user.id), ('id', '=', user.employee_id.id)]"
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xid in (
        "hr_employee_self_only.hr_employee_read_rule_conditional",
        "hr_employee_self_only.hr_employee_public_read_rule_conditional",
    ):
        try:
            rule = env.ref(xid)
        except ValueError:
            _logger.warning("Skipping missing rule %s", xid)
            continue
        rule.write({"domain_force": DOMAIN})
        _logger.info("Updated domain on %s", xid)
