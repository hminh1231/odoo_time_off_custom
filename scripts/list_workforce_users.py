# -*- coding: utf-8 -*-
"""List existing users/employees with workforce visibility for manual testing."""

users = env["res.users"].search(
    [
        ("share", "=", False),
        ("active", "=", True),
        ("employee_id", "!=", False),
    ],
    order="login",
)
print("=== USERS CO NHAN VIEN (de test) ===")
print(f"{'Login':<30} {'Ten':<25} {'WF Group':<8} {'Visibility':<10} {'HR Officer':<12} {'HR Admin'}")
print("-" * 100)
for u in users:
    emp = u.employee_id
    wf = emp.workforce_group or "-"
    vis = emp.employee_visibility or "-"
    is_officer = u.has_group("hr.group_hr_user")
    is_admin = u.has_group("hr.group_hr_manager")
    print(
        f"{u.login:<30} {emp.name[:24]:<25} {wf:<8} {vis:<10} "
        f"{'Yes' if is_officer else 'No':<12} {'Yes' if is_admin else 'No'}"
    )

vp_users = users.filtered(lambda u: u.employee_id.workforce_group == "VP")
ch_users = users.filtered(lambda u: u.employee_id.workforce_group == "CH")
no_wf = users.filtered(lambda u: not u.employee_id.workforce_group)

print()
print(f"Tong: {len(users)} user | VP: {len(vp_users)} | CH: {len(ch_users)} | Chua gan WF: {len(no_wf)}")
if no_wf:
    print("\nCan cap nhat workforce_group cho:")
    for u in no_wf[:10]:
        mien = u.employee_id.mien or "-"
        print(f"  - {u.login} ({u.employee_id.name}) mien={mien}")
