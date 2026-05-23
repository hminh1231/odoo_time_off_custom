# -*- coding: utf-8 -*-
"""One-off: remove duplicate Time Off views still registered under time_off_extra_approval."""
import odoo
from odoo.tools import config

config.parse_config(["-c", "odoo.conf"])
registry = odoo.registry(config["db_name"])
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    names = [
        "view_hr_leave_form_multi_step",
        "view_hr_leave_allocation_form_multi_step",
        "hr_leave_view_kanban_extra_approval",
        "hr_leave_view_list_extra_approval",
        "hr_leave_view_search_waiting_for_me_multi_step",
        "hr_leave_view_form_handover_emergency_banner",
        "hr_leave_view_form_dashboard_handover_emergency",
    ]
    imd = env["ir.model.data"].sudo().search(
        [("module", "=", "time_off_extra_approval"), ("name", "in", names)]
    )
    views = env["ir.ui.view"].sudo().browse(imd.mapped("res_id"))
    print("Removing %s view(s) and %s xmlid(s)" % (len(views), len(imd)))
    views.unlink()
    imd.unlink()
    cr.commit()
    print("Done.")
