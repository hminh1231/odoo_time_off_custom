# -*- coding: utf-8 -*-


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.time_off_extra_approval import hooks

    hooks.sync_leave_type_form_view(env)
