# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env.registry.clear_cache("groups")
    _logger.info("hr_employee_hrm_detail 19.0.1.1.81: visibility privileges UI updated")
