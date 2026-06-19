# -*- coding: utf-8 -*-

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    imd = env["ir.model.data"].sudo()
    row = imd.search(
        [
            ("module", "=", "hr_employee_hrm_detail"),
            ("name", "=", "hr_employee_kanban_hrm_export"),
        ],
        limit=1,
    )
    if not row:
        return
    views = env["ir.ui.view"].sudo().browse(row.res_id).exists()
    if views:
        views.unlink()
    row.unlink()
    _logger.info(
        "hr_employee_hrm_detail: removed hr.employee kanban HRM export inherit "
        "(fields remain on list view for export)"
    )
