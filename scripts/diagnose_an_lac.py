# -*- coding: utf-8 -*-
"""Diagnose why an.lac still sees other departments' time off.

Run: venv\\Scripts\\python.exe odoo\\odoo-bin shell -c odoo.conf -d lap_odoo19 < this
"""


def _show(login):
    user = env["res.users"].search([("login", "=", login)], limit=1)
    if not user:
        user = env["res.users"].search([("login", "ilike", login)], limit=1)
    if not user:
        print("NOT FOUND:", login)
        return
    emp = user.sudo().employee_id
    print("=" * 60)
    print("login:", user.login, "id:", user.id)
    print("visibility_policy:", user.visibility_policy)
    print("employee:", emp.name if emp else None)
    print("employee_ma_bo_phan_id:", user.employee_ma_bo_phan_id.code if user.employee_ma_bo_phan_id else None)
    print("is_hr_manager:", user.has_group("hr.group_hr_manager"))
    print("is_holidays_manager:", user.has_group("hr_holidays.group_hr_holidays_manager"))
    print("is_holidays_user(officer):", user.has_group("hr_holidays.group_hr_holidays_user"))
    leaves = env["hr.leave"].with_user(user).search([])
    codes = {}
    for lv in leaves:
        c = lv.employee_id.ma_bo_phan_id.code or "(none)"
        codes[c] = codes.get(c, 0) + 1
    print("visible_leaves_total:", len(leaves))
    print("visible_leaves_by_ma_bo_phan:", codes)


for lg in ("an.lac@sangtam.com", "nhi.cao@sangtam.com"):
    _show(lg)

rule = env.ref("hr_employee_hrm_detail.hr_leave_peer_read_rule", raise_if_not_found=False)
print("=" * 60)
print("peer rule has ma_bo_phan branch:", bool(rule and "ma_bo_phan'" in (rule.domain_force or "")))
print("module installed version:", env["ir.module.module"].search([("name", "=", "hr_employee_hrm_detail")]).installed_version)
