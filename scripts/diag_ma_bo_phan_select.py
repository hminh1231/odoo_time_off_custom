# -*- coding: utf-8 -*-
"""Diagnose why Mã bộ phận (hr.store.code) cannot be selected on an employee."""

Code = env["hr.store.code"]
total = Code.search_count([])
print("hr.store.code total:", total)

# distinct mien values on store codes
codes = Code.search([])
mien_counts = {}
for c in codes:
    mien_counts[c.mien or "(empty)"] = mien_counts.get(c.mien or "(empty)", 0) + 1
print("store_code mien distribution:", mien_counts)

emp = env["hr.employee"].search([("name", "ilike", "Bùi Thanh Phúc")], limit=1)
if not emp:
    emp = env["hr.employee"].browse(4)
print("employee:", emp.name, "id", emp.id)
print("  mien:", repr(emp.mien))
print("  mien_zone_id:", emp.mien_zone_id.display_name if emp.mien_zone_id else None)
print("  ma_bo_phan_id:", emp.ma_bo_phan_id.code if emp.ma_bo_phan_id else None)
print("  ten_bo_phan:", emp.ten_bo_phan)

# how many codes match the field domain (mien = employee.mien)?
if emp.mien:
    match = Code.search([("mien", "=", emp.mien)])
    print("  codes matching domain [mien =", repr(emp.mien), "]:", len(match),
          match.mapped("code")[:10])
else:
    print("  employee has NO mien -> domain is [] -> all", total, "codes selectable")

# sample of codes with their mien
print("sample codes:", [(c.code, c.mien) for c in codes[:10]])
