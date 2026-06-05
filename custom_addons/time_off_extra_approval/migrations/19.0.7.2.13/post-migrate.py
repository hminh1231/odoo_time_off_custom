# -*- coding: utf-8 -*-
"""Backfill missing store-chain approval lines so OdooBot skip/remind rules apply per step."""

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
        _logger.exception(
            "time_off_extra_approval: store-chain approval line sync failed during migration"
        )
