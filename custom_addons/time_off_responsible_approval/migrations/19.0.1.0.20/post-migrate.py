import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    pending = env["hr.leave"].search(
        [
            ("state", "in", ("confirm", "validate1")),
            ("validation_type", "=", "employee_hr_responsibles"),
        ]
    )
    if pending:
        pending._ensure_responsible_approval_lines()
        pending._refresh_responsible_actionable_users()
        _logger.info(
            "time_off_responsible_approval: repaired actionable users for %s pending leave(s)",
            len(pending),
        )

    leaves = env["hr.leave"].search(
        [
            ("employee_id", "!=", False),
            ("state", "in", ("confirm", "validate1", "validate", "refuse")),
        ]
    )
    if leaves:
        leaves._compute_special_readonly_notifier_user_ids()
        leaves.flush_recordset(["special_readonly_notifier_user_ids"])
        _logger.info(
            "time_off_responsible_approval: refreshed special read-only notifier users for %s leave(s)",
            len(leaves),
        )
