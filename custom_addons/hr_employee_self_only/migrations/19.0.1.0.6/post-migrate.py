# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Remove read-only ir.rule records; privacy is enforced via Personal tab visibility instead."""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

RULE_XMLIDS = (
    "hr_employee_self_only.hr_employee_read_rule_conditional",
    "hr_employee_self_only.hr_employee_public_read_rule_conditional",
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xid in RULE_XMLIDS:
        try:
            rule = env.ref(xid)
        except ValueError:
            continue
        _logger.info("Removing obsolete record rule %s", xid)
        rule.unlink()
