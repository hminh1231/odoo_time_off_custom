# -*- coding: utf-8 -*-
"""Verify 4 manual test-plan steps for HR workforce visibility + Discuss."""

from odoo.tests import new_test_user

from odoo.addons.mail.tools.discuss import Store


def _step(title, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {title}")
    if detail:
        print(f"       {detail}")
    return ok


company = env.company
tag = "verify_workforce_"

# --- setup isolated users for this run ---
vp_user = new_test_user(env, login=f"{tag}vp", groups="hr.group_hr_user")
ch_user = new_test_user(env, login=f"{tag}ch", groups="hr.group_hr_user")
admin_user = new_test_user(env, login=f"{tag}admin", groups="hr.group_hr_manager")

vp_officer = env["hr.employee"].create(
    {
        "name": "Verify VP Officer",
        "user_id": vp_user.id,
        "company_id": company.id,
        "mien": "VP",
        "workforce_group": "VP",
        "employee_visibility": "office",
    }
)
vp_colleague = env["hr.employee"].create(
    {
        "name": "Verify VP Colleague",
        "company_id": company.id,
        "mien": "VP",
        "workforce_group": "VP",
        "employee_visibility": "office",
    }
)
ch_officer = env["hr.employee"].create(
    {
        "name": "Verify CH Officer",
        "user_id": ch_user.id,
        "company_id": company.id,
        "workforce_group": "CH",
        "employee_visibility": "store",
    }
)
ch_colleague = env["hr.employee"].create(
    {
        "name": "Verify CH Colleague",
        "company_id": company.id,
        "workforce_group": "CH",
        "employee_visibility": "store",
    }
)
env.flush_all()
vp_user.invalidate_recordset(["employee_id", "hr_user_workforce_scope"])
ch_user.invalidate_recordset(["employee_id", "hr_user_workforce_scope"])

results = []

# Step 1: VP Officer chỉ thấy hồ sơ office
vp_visible = set(env["hr.employee"].with_user(vp_user).search([]).ids)
results.append(
    _step(
        "1. VP Officer chỉ thấy hồ sơ office",
        vp_officer.id in vp_visible
        and vp_colleague.id in vp_visible
        and ch_colleague.id not in vp_visible,
        f"visible={sorted(vp_visible)}",
    )
)

# Step 2: CH Officer chỉ thấy hồ sơ store
ch_visible = set(env["hr.employee"].with_user(ch_user).search([]).ids)
results.append(
    _step(
        "2. CH Officer chỉ thấy hồ sơ store",
        ch_officer.id in ch_visible
        and ch_colleague.id in ch_visible
        and vp_colleague.id not in ch_visible,
        f"visible={sorted(ch_visible)}",
    )
)

# Step 3: HR Admin thấy toàn bộ
admin_visible = set(env["hr.employee"].with_user(admin_user).search([]).ids)
results.append(
    _step(
        "3. HR Admin thấy toàn bộ hồ sơ VP + CH",
        vp_colleague.id in admin_visible and ch_colleague.id in admin_visible,
        f"count={len(admin_visible)}",
    )
)

# Step 4: Discuss VP tìm/invite CH (và ngược lại)
Partner = env["res.partner"]
vp_invite = Partner.with_user(vp_user)._search_for_channel_invite(
    Store(), ch_user.name, limit=30
)
ch_invite = Partner.with_user(ch_user)._search_for_channel_invite(
    Store(), vp_user.name, limit=30
)
vp_finds_ch = ch_user.partner_id.id in vp_invite.get("partner_ids", [])
ch_finds_vp = vp_user.partner_id.id in ch_invite.get("partner_ids", [])
results.append(
    _step(
        "4. Discuss: VP invite CH và CH invite VP",
        vp_finds_ch and ch_finds_vp,
        f"vp_invite_ids={vp_invite.get('partner_ids')} ch_invite_ids={ch_invite.get('partner_ids')}",
    )
)

print("---")
print("ALL PASS" if all(results) else "SOME FAILED")
