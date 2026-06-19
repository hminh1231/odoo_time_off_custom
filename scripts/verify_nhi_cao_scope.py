# -*- coding: utf-8 -*-
"""Verify nhi.cao@sangtam.com sees only CH Miền Nam employees."""

user = env["res.users"].search([("login", "=", "nhi.cao@sangtam.com")], limit=1)
if not user:
    print("FAIL: user nhi.cao@sangtam.com not found")
else:
    emp = user.employee_id
    print("user", user.id, "scope", user.hr_user_workforce_scope)
    print(
        "employee",
        emp.name if emp else None,
        "mien",
        emp.mien if emp else None,
        "workforce_group",
        emp.workforce_group if emp else None,
        "visibility",
        emp.employee_visibility if emp else None,
    )
    visible = env["hr.employee"].with_user(user).search([])
    print("visible_count", len(visible))
    vp_count = visible.filtered(lambda e: e.workforce_group == "VP" or e.mien == "VP")
    ch_bac = visible.filtered(lambda e: (e.mien or (e.ma_bo_phan_id.mien if e.ma_bo_phan_id else False)) == "Bắc")
    ch_dtt = visible.filtered(lambda e: (e.mien or (e.ma_bo_phan_id.mien if e.ma_bo_phan_id else False)) == "ĐTT")
    ch_nam = visible.filtered(lambda e: (e.mien or (e.ma_bo_phan_id.mien if e.ma_bo_phan_id else False)) == "Nam")
    unclassified = visible.filtered(lambda e: not e.workforce_group and not e.employee_visibility)
    print("vp_in_visible", len(vp_count), vp_count.mapped("name")[:5])
    print("ch_bac_in_visible", len(ch_bac))
    print("ch_dtt_in_visible", len(ch_dtt))
    print("ch_nam_in_visible", len(ch_nam))
    print("unclassified_in_visible", len(unclassified))
    ok = (
        user.hr_user_workforce_scope == "ch_nam"
        and len(vp_count) == 0
        and len(ch_bac) == 0
        and len(ch_dtt) == 0
    )
    print("RESULT", "PASS" if ok else "FAIL")
