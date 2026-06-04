# -*- coding: utf-8 -*-

import logging

from odoo.tools import sql

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if sql.table_exists(cr, "hr_leave_odoobot_notify_config"):
        _logger.info("time_off_extra_approval: dropping legacy hr_leave_odoobot_notify_config")
        cr.execute("DROP TABLE IF EXISTS hr_leave_odoobot_notify_config CASCADE")
    if not sql.column_exists(cr, "hr_leave", "approval_last_odoobot_remind_slot"):
        cr.execute(
            """
            ALTER TABLE hr_leave
            ADD COLUMN approval_last_odoobot_remind_slot VARCHAR
            """
        )
    if not sql.column_exists(cr, "hr_leave", "handover_last_odoobot_remind_at"):
        cr.execute(
            """
            ALTER TABLE hr_leave
            ADD COLUMN handover_last_odoobot_remind_at TIMESTAMP WITHOUT TIME ZONE
            """
        )
    if not sql.column_exists(cr, "hr_leave", "handover_last_odoobot_remind_slot"):
        cr.execute(
            """
            ALTER TABLE hr_leave
            ADD COLUMN handover_last_odoobot_remind_slot VARCHAR
            """
        )
