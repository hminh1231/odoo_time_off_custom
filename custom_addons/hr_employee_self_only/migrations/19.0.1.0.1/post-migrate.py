# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Remove superseded ir.rule records from 19.0.1.0.0 (grouped rules ORed with HR officer)."""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

OLD_XMLIDS = (
    "hr_employee_self_only.hr_employee_rule_internal_user_self_read_only",
    "hr_employee_self_only.hr_employee_rule_hr_officer_full_read",
    "hr_employee_self_only.hr_employee_public_rule_internal_user_self_read_only",
    "hr_employee_self_only.hr_employee_public_rule_hr_officer_full_read",
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xid in OLD_XMLIDS:
        try:
            rec = env.ref(xid)
        except ValueError:
            continue
        _logger.info("Removing obsolete record rule: %s", xid)
        rec.unlink()
