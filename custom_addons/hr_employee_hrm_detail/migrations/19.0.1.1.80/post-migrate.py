# -*- coding: utf-8 -*-

import logging

from odoo import SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api

    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.hr_employee_hrm_detail.hooks import (
        _sync_mien_access_rules,
        _sync_user_visibility_groups,
    )

    users = env["res.users"].search([("share", "=", False)])
    _sync_user_visibility_groups(env, users)
    _sync_mien_access_rules(env)
    env.registry.clear_cache()
    _logger.info(
        "hr_employee_hrm_detail 19.0.1.1.80: visibility groups synced for %s users",
        len(users),
    )
