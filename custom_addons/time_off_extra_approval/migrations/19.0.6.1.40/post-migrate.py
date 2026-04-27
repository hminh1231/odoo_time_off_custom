# -*- coding: utf-8 -*-
"""Backfill hr.leave.handover.acceptance.assigned_by_user_id from the leave requester."""

import logging

from odoo.tools import sql

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not sql.column_exists(cr, "hr_leave_handover_acceptance", "assigned_by_user_id"):
        return
    cr.execute(
        """
        UPDATE hr_leave_handover_acceptance AS hla
        SET assigned_by_user_id = he.user_id
        FROM hr_leave AS hl
        JOIN hr_employee AS he ON he.id = hl.employee_id
        WHERE hla.leave_id = hl.id
          AND hla.assigned_by_user_id IS NULL
          AND he.user_id IS NOT NULL
        """
    )
    n = cr.rowcount
    if n:
        _logger.info(
            "time_off_extra_approval: backfilled assigned_by_user_id on %s handover acceptance row(s)",
            n,
        )
