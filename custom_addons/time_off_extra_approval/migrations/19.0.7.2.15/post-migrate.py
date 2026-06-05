# -*- coding: utf-8 -*-
"""Reconcile store-chain approval lines after RSM/org-chain fix."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    leaves = env["hr.leave"].search(
        [
            ("state", "in", ("confirm", "validate1")),
            ("validation_type", "in", ("employee_hr_responsibles", "vp_chain")),
            ("employee_id", "!=", False),
        ]
    )
    if not leaves:
        return
    try:
        leaves._ensure_responsible_approval_lines()
    except Exception:
        _logger.exception("time_off_extra_approval: reconcile store-chain lines failed")
