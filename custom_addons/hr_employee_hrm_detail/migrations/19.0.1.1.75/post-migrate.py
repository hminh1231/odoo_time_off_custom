# -*- coding: utf-8 -*-

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo.addons.hr_employee_hrm_detail.hooks import _sync_mien_access_rules

    env = api.Environment(cr, SUPERUSER_ID, {})
    users = env["res.users"].search([])
    env.add_to_compute(env["res.users"]._fields["hr_user_workforce_scope"], users)
    env["res.users"].flush_model(["hr_user_workforce_scope"])
    _sync_mien_access_rules(env)
    env["hr.employee.public"].init()
    env.registry.clear_cache()
    _logger.info(
        "hr_employee_hrm_detail: regional CH supporters scoped; workforce scope recomputed"
    )
