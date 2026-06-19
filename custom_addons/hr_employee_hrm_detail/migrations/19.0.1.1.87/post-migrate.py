# -*- coding: utf-8 -*-
"""Add the 'ma_bo_phan' (Cùng mã bộ phận) visibility policy.

Re-syncs the managed ir.rule domains (so the hr.leave peer-read rule learns the
new policy branch) and switches nhi.cao@sangtam.com to the new policy: she now
only sees employees / time off requests whose Mã bộ phận matches her own
(LUG_KDV), plus her own records.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.hr_employee_hrm_detail.hooks import _sync_mien_access_rules

    _sync_mien_access_rules(env)

    user = env["res.users"].search(
        [("login", "=", "nhi.cao@sangtam.com")], limit=1
    )
    if user:
        user.visibility_policy = "ma_bo_phan"
        _logger.info(
            "hr_employee_hrm_detail 19.0.1.1.87: set %s -> visibility_policy=ma_bo_phan",
            user.login,
        )
    else:
        _logger.warning(
            "hr_employee_hrm_detail 19.0.1.1.87: user nhi.cao@sangtam.com not found"
        )

    env.registry.clear_cache()
    _logger.info(
        "hr_employee_hrm_detail 19.0.1.1.87: re-synced ir.rule domains "
        "(added 'ma_bo_phan' policy)"
    )
