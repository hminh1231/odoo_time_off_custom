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


_LEGACY_VIEW_MODULES = ("time_off_extra_approval", "time_off_responsible_approval")
_LEGACY_VIEW_NAMES = (
    "view_hr_leave_form_multi_step",
    "view_hr_leave_allocation_form_multi_step",
    "hr_leave_view_kanban_extra_approval",
    "hr_leave_view_list_extra_approval",
    "hr_leave_view_search_waiting_for_me_multi_step",
    "hr_leave_view_form_handover_emergency_banner",
    "hr_leave_view_form_dashboard_handover_emergency",
)


def cleanup_duplicate_hr_leave_views(env):
    """Remove hr.leave views still registered under legacy modules after the split."""
    imd = env["ir.model.data"].sudo()
    rows = imd.search(
        [
            ("module", "in", list(_LEGACY_VIEW_MODULES)),
            ("name", "in", list(_LEGACY_VIEW_NAMES)),
        ]
    )
    if not rows:
        return 0
    views = env["ir.ui.view"].sudo().browse(rows.mapped("res_id")).exists()
    count = len(views)
    views.unlink()
    rows.unlink()
    return count


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
    cleanup_duplicate_hr_leave_views(env)
