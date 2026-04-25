# -*- coding: utf-8 -*-
"""Deactivate stray Studio inherits that duplicate multi-step UI (canonical arch comes from XML)."""


def sync_leave_type_form_view(env):
    try:
        view = env.ref("time_off_extra_approval.view_hr_leave_type_form_extra_approvers")
    except ValueError:
        return
    orphans = env["ir.ui.view"].search(
        [
            "&",
            "&",
            ("model", "=", "hr.leave.type"),
            ("id", "!=", view.id),
            "|",
            ("arch_db", "ilike", "multi_step_user_1"),
            ("arch_db", "ilike", "multi_step_approver_employee_1"),
        ]
    )
    if orphans:
        orphans.write({"active": False})


def post_init_hook(env):

    sync_leave_type_form_view(env)
    pending = env["hr.leave"].search([("state", "in", ("confirm", "validate1"))])
    if pending:
        pending._compute_approval_actionable_user_ids()
