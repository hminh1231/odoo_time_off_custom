# -*- coding: utf-8 -*-

def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.lug_permission.hooks import _sync_lug_leave_access_rules

    _sync_lug_leave_access_rules(env)
