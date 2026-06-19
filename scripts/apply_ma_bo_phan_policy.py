# -*- coding: utf-8 -*-
"""Re-sync the hr.leave peer-read rule and switch named users to 'ma_bo_phan'.

Applies the 'Cùng mã bộ phận' time off visibility to the running DB without a
full module upgrade. Run:
  venv\\Scripts\\python.exe odoo\\odoo-bin shell -c odoo.conf -d lap_odoo19 < this
"""
from odoo.addons.hr_employee_hrm_detail.hooks import _sync_mien_access_rules

_sync_mien_access_rules(env)

LOGINS = ("an.lac@sangtam.com", "nhi.cao@sangtam.com")
for login in LOGINS:
    user = env["res.users"].search([("login", "=", login)], limit=1)
    if not user:
        print("NOT FOUND:", login)
        continue
    user.visibility_policy = "ma_bo_phan"
    print("SET", login, "-> ma_bo_phan; own ma_bo_phan =",
          user.employee_ma_bo_phan_id.code if user.employee_ma_bo_phan_id else None)

env.cr.commit()
env.registry.clear_cache()

rule = env.ref("hr_employee_hrm_detail.hr_leave_peer_read_rule")
print("rule has ma_bo_phan branch:", "ma_bo_phan'" in (rule.domain_force or ""))

for login in LOGINS:
    user = env["res.users"].search([("login", "=", login)], limit=1)
    if not user:
        continue
    leaves = env["hr.leave"].with_user(user).search([])
    codes = {}
    for lv in leaves:
        c = lv.employee_id.ma_bo_phan_id.code or "(none)"
        codes[c] = codes.get(c, 0) + 1
    print("AFTER", login, "policy:", user.visibility_policy,
          "visible_leaves:", len(leaves), codes)
