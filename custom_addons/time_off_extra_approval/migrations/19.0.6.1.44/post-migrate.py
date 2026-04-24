# -*- coding: utf-8 -*-
"""Ensure hr_leave_handover_acceptance.reassigned_by_escalation_owner exists in the database."""

import logging

from odoo.tools import sql

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if sql.column_exists(cr, "hr_leave_handover_acceptance", "reassigned_by_escalation_owner"):
        return
    cr.execute(
        """
        ALTER TABLE hr_leave_handover_acceptance
        ADD COLUMN reassigned_by_escalation_owner boolean DEFAULT false NOT NULL
        """
    )
    _logger.info(
        "time_off_extra_approval: added column reassigned_by_escalation_owner on hr_leave_handover_acceptance"
    )
