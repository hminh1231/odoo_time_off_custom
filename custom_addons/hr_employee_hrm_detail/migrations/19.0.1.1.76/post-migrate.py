# -*- coding: utf-8 -*-

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Zone = env["hr.mien.zone"]
    employees = env["hr.employee"].with_context(active_test=False).search([])
    for employee in employees:
        if not employee.mien:
            continue
        zone = Zone.zone_from_legacy_mien(employee.mien)
        if zone and employee.mien_zone_id != zone:
            employee.write({"mien_zone_id": zone.id})
    env["hr.employee.public"].init()
    _logger.info(
        "hr_employee_hrm_detail: backfilled mien_zone_id for VP/CH hierarchy sidebar"
    )
