# Recompute HRM leave counters after read_group field name fix (Odoo 19).

def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    employees = env["hr.employee"].search([("tong_so_phep", "!=", False)])
    if employees:
        employees._compute_time_off_summary()
