# -*- coding: utf-8 -*-

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo.addons.hr_employee_hrm_detail.hooks import _sync_mien_access_rules

    env = api.Environment(cr, SUPERUSER_ID, {})
    _sync_mien_access_rules(env)
    env.registry.clear_cache()
    _logger.info(
        "hr_employee_hrm_detail: re-synced officer visibility ir.rule domains (self-scope fix)"
    )
