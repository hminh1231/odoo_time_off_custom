# -*- coding: utf-8 -*-
"""Cap Time Off Officers via a global 'Cùng mã bộ phận' hr.leave read rule.

The peer-read rule is a *group* rule, so it is OR-combined with the standard
"Officer: manage all requests" rule and cannot restrict an Officer. The new
global rule (loaded from security/hr_leave_ma_bo_phan_scope_security.xml) is
AND-ed with every leave rule and therefore caps Officers too.

This migration re-syncs the managed ir.rule domains and (re)applies the
'ma_bo_phan' policy to the named example users.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.hr_employee_hrm_detail.hooks import _sync_mien_access_rules

    _sync_mien_access_rules(env)

    for login in ("an.lac@sangtam.com", "nhi.cao@sangtam.com"):
        user = env["res.users"].search([("login", "=", login)], limit=1)
        if user:
            user.visibility_policy = "ma_bo_phan"
            _logger.info(
                "hr_employee_hrm_detail 19.0.1.1.89: %s -> visibility_policy=ma_bo_phan",
                login,
            )

    env.registry.clear_cache()
    _logger.info(
        "hr_employee_hrm_detail 19.0.1.1.89: global Cùng mã bộ phận leave rule active"
    )
