# -*- coding: utf-8 -*-
"""Read-only verification of the 'Cùng mã bộ phận' time off visibility."""

rule = env.ref("hr_employee_hrm_detail.hr_leave_ma_bo_phan_scope_rule",
               raise_if_not_found=False)
print("global rule exists:", bool(rule), "| global(groups empty):",
      (rule and not rule.groups) if rule else None,
      "| perm_read:", rule.perm_read if rule else None)

for login in ("an.lac@sangtam.com", "nhi.cao@sangtam.com"):
    u = env["res.users"].search([("login", "=", login)], limit=1)
    if not u:
        print("NOT FOUND", login)
        continue
    leaves = env["hr.leave"].with_user(u).search([])
    by_code, errors = {}, []
    for lv in leaves:
        try:
            _ = lv.employee_id.display_name
            c = lv.employee_id.ma_bo_phan_id.code or "(none)"
        except Exception as e:
            errors.append((lv.id, type(e).__name__))
            continue
        by_code[c] = by_code.get(c, 0) + 1
    print("USER", login,
          "| policy", u.visibility_policy,
          "| own_code", u.employee_ma_bo_phan_id.code if u.employee_ma_bo_phan_id else None,
          "| officer", u.has_group("hr_holidays.group_hr_holidays_user"),
          "| visible_leaves", len(leaves),
          "| by_code", by_code,
          "| read_errors", errors)
