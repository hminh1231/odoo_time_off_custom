# -*- coding: utf-8 -*-
"""Split cancel permission from delete and preserve existing user access."""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    delete_group = env.ref(
        "hr_leave_delete_cancel.group_hr_holidays_leave_delete",
        raise_if_not_found=False,
    )
    cancel_group = env.ref(
        "hr_leave_delete_cancel.group_hr_holidays_leave_cancel",
        raise_if_not_found=False,
    )
    if delete_group and cancel_group:
        users_with_delete = env["res.users"].search(
            [("group_ids", "in", delete_group.id)]
        )
        users_to_update = users_with_delete.filtered(
            lambda user: cancel_group not in user.group_ids
        )
        if users_to_update:
            users_to_update.write({"group_ids": [(4, cancel_group.id)]})
            _logger.info(
                "Granted cancel time off permission to %s users with delete permission",
                len(users_to_update),
            )

    for xml_id, sequence in (
        ("hr_leave_delete_cancel.res_groups_privilege_leave_delete", 12),
        ("hr_leave_delete_cancel.res_groups_privilege_leave_cancel", 13),
        ("hr_employee_self_only.res_groups_privilege_employee_edit", 14),
        ("hr_employee_self_only.res_groups_privilege_view_personal", 15),
    ):
        privilege = env.ref(xml_id, raise_if_not_found=False)
        if privilege:
            privilege.write({"sequence": sequence})

    env.registry.clear_cache()
