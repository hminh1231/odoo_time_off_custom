# -*- coding: utf-8 -*-
"""Backfill missing HR Responsibles approval lines for To Approve requests."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    broken = env["hr.leave"].search(
        [
            ("state", "=", "confirm"),
            ("validation_type", "=", "employee_hr_responsibles"),
            ("employee_id", "!=", False),
            ("responsible_approval_line_ids", "=", False),
        ]
    )
    for leave in broken:
        try:
            leave._ensure_responsible_approval_lines()
        except Exception as exc:
            _logger.warning(
                "time_off_extra_approval: could not init approval lines for leave id=%s: %s",
                leave.id,
                exc,
            )
    if broken:
        broken._compute_approval_actionable_user_ids()
