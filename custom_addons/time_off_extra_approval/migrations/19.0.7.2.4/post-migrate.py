# -*- coding: utf-8 -*-

def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    rules = env["hr.leave.odoobot.notify.rule"].search([])
    if rules:
        rules._compute_display_name()
        rules._compute_display_labels()
        rules._compute_remind_display()
        rules._compute_skip_level_display()
