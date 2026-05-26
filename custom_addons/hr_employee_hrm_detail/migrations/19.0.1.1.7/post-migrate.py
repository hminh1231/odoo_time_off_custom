# Recalculate leave balance: only validated (approved) requests deduct days.

def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    employees = env["hr.employee"].search([])
    if employees:
        employees._compute_time_off_summary()
