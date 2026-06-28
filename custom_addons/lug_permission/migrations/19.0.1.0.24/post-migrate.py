# -*- coding: utf-8 -*-

def migrate(cr, version):
    from odoo import api

    env = api.Environment(cr, 1, {})
    env["res.users"]._lug_cleanup_legacy_visibility_views()
    from odoo.addons.lug_permission.hooks import _sync_lug_leave_access_rules

    _sync_lug_leave_access_rules(env)
    enforced = env["res.users"].search([]).filtered(
        lambda user: user._lug_permission_is_enforced()
    )
    if enforced:
        enforced._sync_lug_odoo_groups()
    env.registry.clear_cache()
