# -*- coding: utf-8 -*-
"""Create the global 'Cùng mã bộ phận' hr.leave read rule, set the two test
users to the policy, then simulate the Time Off list (read employee display)
to detect any leave/employee visibility mismatch (MissingError)."""

DOMAIN = (
    "[(1, '=', 1)] if (user.has_group('hr_holidays.group_hr_holidays_manager') "
    "or user.has_group('hr.group_hr_manager') "
    "or (user.visibility_policy or 'self') != 'ma_bo_phan') else "
    "((['|', '|', '|', '|', '|', "
    "('employee_id.ma_bo_phan_id', '=', user.employee_ma_bo_phan_id.id), "
    "('employee_id.user_id', '=', user.id), "
    "('employee_id', '=', user.employee_id.id), "
    "('employee_id.leave_manager_id', '=', user.id), "
    "('approval_actionable_user_ids', 'in', [user.id]), "
    "('special_readonly_notifier_user_ids', 'in', [user.id])]) "
    "if user.employee_ma_bo_phan_id else "
    "(['|', '|', '|', '|', "
    "('employee_id.user_id', '=', user.id), "
    "('employee_id', '=', user.employee_id.id), "
    "('employee_id.leave_manager_id', '=', user.id), "
    "('approval_actionable_user_ids', 'in', [user.id]), "
    "('special_readonly_notifier_user_ids', 'in', [user.id])]))"
)

XMLID = "hr_employee_hrm_detail.hr_leave_ma_bo_phan_scope_rule"
model = env["ir.model"].search([("model", "=", "hr.leave")], limit=1)
rule = env.ref(XMLID, raise_if_not_found=False)
vals = {
    "name": "Đơn nghỉ phép: lọc theo Cùng mã bộ phận",
    "model_id": model.id,
    "groups": [(6, 0, [])],
    "perm_read": True,
    "perm_write": False,
    "perm_create": False,
    "perm_unlink": False,
    "domain_force": DOMAIN,
}
if rule:
    rule.write(vals)
    print("UPDATED rule", rule.id)
else:
    rule = env["ir.rule"].create(vals)
    module, name = XMLID.split(".")
    env["ir.model.data"].create({
        "module": module, "name": name,
        "model": "ir.rule", "res_id": rule.id, "noupdate": False,
    })
    print("CREATED rule", rule.id)

for login in ("an.lac@sangtam.com", "nhi.cao@sangtam.com"):
    u = env["res.users"].search([("login", "=", login)], limit=1)
    if u:
        u.visibility_policy = "ma_bo_phan"
        print("SET", login, "-> ma_bo_phan, code=",
              u.employee_ma_bo_phan_id.code if u.employee_ma_bo_phan_id else None)

env.cr.commit()
env.registry.clear_cache()

print("\n--- SIMULATE TIME OFF LIST ---")
for login in ("an.lac@sangtam.com", "nhi.cao@sangtam.com"):
    u = env["res.users"].search([("login", "=", login)], limit=1)
    leaves = env["hr.leave"].with_user(u).search([])
    by_code = {}
    errors = []
    for lv in leaves:
        try:
            name = lv.employee_id.display_name
            code = lv.employee_id.ma_bo_phan_id.code or "(none)"
        except Exception as e:
            errors.append((lv.id, type(e).__name__))
            continue
        by_code[code] = by_code.get(code, 0) + 1
    print(login, "policy", u.visibility_policy,
          "code", u.employee_ma_bo_phan_id.code if u.employee_ma_bo_phan_id else None)
    print("   visible_leaves:", len(leaves), "by_code:", by_code)
    print("   EMPLOYEE_READ_ERRORS:", errors)
