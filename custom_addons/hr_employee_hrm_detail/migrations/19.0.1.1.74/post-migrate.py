# -*- coding: utf-8 -*-

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo.addons.hr_employee_hrm_detail.hooks import _sync_mien_access_rules
    from odoo.addons.hr_employee_hrm_detail.models.hr_employee import (
        STORE_MIENS,
        VISIBILITY_OFFICE,
        VISIBILITY_STORE,
        WORKFORCE_GROUP_CH,
        WORKFORCE_GROUP_VP,
    )

    env = api.Environment(cr, SUPERUSER_ID, {})
    employees = env["hr.employee"].with_context(active_test=False).search([])
    for employee in employees:
        mien = employee.mien or (
            employee.ma_bo_phan_id.mien if employee.ma_bo_phan_id else False
        )
        workforce_group = employee.workforce_group
        if not workforce_group:
            if mien == WORKFORCE_GROUP_VP:
                workforce_group = WORKFORCE_GROUP_VP
            elif mien in STORE_MIENS:
                workforce_group = WORKFORCE_GROUP_CH
        visibility = employee.employee_visibility
        if visibility not in (VISIBILITY_OFFICE, VISIBILITY_STORE, "all"):
            if workforce_group == WORKFORCE_GROUP_VP:
                visibility = VISIBILITY_OFFICE
            elif workforce_group == WORKFORCE_GROUP_CH:
                visibility = VISIBILITY_STORE
            else:
                visibility = False
        write_vals = {}
        if workforce_group and employee.workforce_group != workforce_group:
            write_vals["workforce_group"] = workforce_group
        if visibility and employee.employee_visibility != visibility:
            write_vals["employee_visibility"] = visibility
        if write_vals:
            employee.write(write_vals)

    users = env["res.users"].search([])
    env.add_to_compute(env["res.users"]._fields["hr_user_workforce_scope"], users)
    env["res.users"].flush_model(["hr_user_workforce_scope"])
    _sync_mien_access_rules(env)
    env["hr.employee.public"].init()
    env.registry.clear_cache()
    _logger.info(
        "hr_employee_hrm_detail: CH officers scoped by miền Bắc/Nam/ĐTT; workforce data synced"
    )
