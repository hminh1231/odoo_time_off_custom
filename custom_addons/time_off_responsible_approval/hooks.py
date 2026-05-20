# -*- coding: utf-8 -*-


def _repoint_xmlid(env, old_module, old_name, new_module, new_name):
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
    _repoint_xmlid(
        env,
        "time_off_extra_approval",
        "ir_cron_escalate_responsible_approval",
        "time_off_responsible_approval",
        "ir_cron_escalate_responsible_approval",
    )
