## Summary
- Kết hợp Phương án 1 (tách quyền HR khỏi Chat) và Phương án 5 (Visibility Layer + Communication Layer) trong module `hr_employee_hrm_detail`.
- Thêm `workforce_group` (VP/CH) và `employee_visibility` (office/store/all) trên `hr.employee`; record rule chỉ áp dụng lớp HR (VP thấy VP, CH thấy CH, Admin không giới hạn).
- Gỡ filter HR trên Discuss (`res.partner`): mọi user nội bộ đều tìm được nhau để chat, trong khi mở hồ sơ nhân viên vẫn bị giới hạn theo visibility.

## Test plan
- [x] Upgrade module `hr_employee_hrm_detail` lên 19.0.1.1.73
- [x] Chạy `TestWorkforceVisibilityDiscuss` (6 tests passed)
- [x] Đăng nhập user VP (Officer): chỉ thấy hồ sơ `employee_visibility=office`
- [x] Đăng nhập user CH (Officer): chỉ thấy hồ sơ `employee_visibility=store`
- [x] Đăng nhập HR Admin: thấy toàn bộ hồ sơ
- [x] Trong Discuss, user VP tìm/invite được user CH (và ngược lại)

## Verify locally
```powershell
python odoo-bin -c odoo.conf -d lap_odoo19 -u hr_employee_hrm_detail --stop-after-init --test-tags /hr_employee_hrm_detail:TestWorkforceVisibilityDiscuss

Get-Content -Encoding UTF8 scripts/verify_workforce_visibility.py | python odoo-bin shell -c odoo.conf -d lap_odoo19 --no-http
```
