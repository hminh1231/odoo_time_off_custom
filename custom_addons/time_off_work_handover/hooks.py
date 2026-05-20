# -*- coding: utf-8 -*-


def _repoint_xmlid(env, old_module, old_name, new_module, new_name):
    """Keep existing DB rows when xmlid module/name changes during split."""
    old = f"{old_module}.{old_name}"
    new = f"{new_module}.{new_name}"
    if old == new:
        return
    imd = env["ir.model.data"].sudo()
    row = imd.search([("module", "=", old_module), ("name", "=", old_name)], limit=1)
    if not row:
        return
    conflict = imd.search([("module", "=", new_module), ("name", "=", new_name)], limit=1)
    if conflict and conflict.res_id != row.res_id:
        return
    row.write({"module": new_module, "name": new_name})


def post_init_hook(env):
    for old_name, new_name in (
        ("mail_act_leave_work_handover", "mail_act_leave_work_handover"),
        ("ir_cron_escalate_handover_timeouts", "ir_cron_escalate_handover_timeouts"),
        ("hr_leave_rule_handover_recipient_read", "hr_leave_rule_handover_recipient_read"),
    ):
        _repoint_xmlid(
            env,
            "time_off_extra_approval",
            old_name,
            "time_off_work_handover",
            new_name,
        )
