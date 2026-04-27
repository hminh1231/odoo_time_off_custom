# -*- coding: utf-8 -*-
"""Recompute approval_actionable_user_ids for pending requests after upgrade."""


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    pending = env["hr.leave"].search([("state", "in", ("confirm", "validate1"))])
    if pending:
        pending._compute_approval_actionable_user_ids()
