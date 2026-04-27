# -*- coding: utf-8 -*-
"""Ensure hr_leave.is_emergency_leave exists (fixes DBs where the column was never created)."""

import logging

from odoo.tools import sql

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if sql.column_exists(cr, "hr_leave", "is_emergency_leave"):
        return
    _logger.info("time_off_extra_approval: adding missing column hr_leave.is_emergency_leave")
    sql.create_column(cr, "hr_leave", "is_emergency_leave", "boolean")
