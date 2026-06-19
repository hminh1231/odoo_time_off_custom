# -*- coding: utf-8 -*-
"""Find leaves visible to a user whose employee record is NOT readable by them."""

login = "an.lac@sangtam.com"
user = env["res.users"].search([("login", "=", login)], limit=1)
print("user", login, "policy", user.visibility_policy,
      "code", user.employee_ma_bo_phan_id.code if user.employee_ma_bo_phan_id else None,
      "emp_id", user.employee_id.id)

leaves = env["hr.leave"].with_user(user).search([])
print("visible_leaves:", len(leaves))
readable_emp_ids = set(env["hr.employee"].with_user(user).search([]).ids)
print("readable_employee_ids:", sorted(readable_emp_ids))

for lv in leaves:
    emp_id = lv.employee_id.id
    readable = emp_id in readable_emp_ids
    # why visible? check the self/approval leaves
    emp = env["hr.employee"].sudo().browse(emp_id)
    print(
        "leave", lv.id,
        "| emp", emp_id, emp.name,
        "| code", emp.ma_bo_phan_id.code,
        "| leave_manager==me", emp.leave_manager_id.id == user.id,
        "| EMP_READABLE", readable,
    )
