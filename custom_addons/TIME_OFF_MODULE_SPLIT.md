# Tách `time_off_extra_approval` thành nhiều custom module

## Kiến trúc đề xuất

```
hr_holidays ──┬── business_discuss_bots
              │
              ├── time_off_work_handover          (bàn giao công việc)
              │         └── models: hr.leave.handover.*, hr_leave_handover.py
              │
              ├── time_off_responsible_approval   (duyệt HR responsibles / multi-step)
              │         └── depends: + hr_employee_multi_responsible, hr_job_title_vn
              │         └── depends: time_off_work_handover (gọi _handover_ready_for_approval)
              │
              └── time_off_extra_approval         (cấu hình loại nghỉ, emergency, glue)
                        └── depends: cả hai module trên
```

## Phân chia trách nhiệm

| Module | Nội dung chính |
|--------|----------------|
| **time_off_work_handover** | `handover_*` fields, nhận/từ chối/thay người, escalation cron, OdooBot Bàn giao, activity Work Handover |
| **time_off_responsible_approval** | `responsible_approval_line_ids`, org chart, multi-step 6, extra approvers compute, OdooBot Duyệt đơn, cron timeout duyệt |
| **time_off_extra_approval** | `hr.leave.type` config, emergency leave, discuss deep link, `write`/`create`/`action_confirm` điều phối, views tổng |

## Thứ tự `super()` trên `hr.leave`

Module phụ thuộc load sau → `write()` chạy trước:

1. `time_off_extra_approval` (emergency + điều phối submit/outcome)
2. `time_off_responsible_approval` (dòng duyệt, notify approver)
3. `time_off_work_handover` (sync handover, bot bàn giao)
4. `hr_holidays` (core)

## Migration database (production)

Sau khi cài module mới, chạy upgrade theo thứ tự:

1. Cài `time_off_work_handover`
2. Cài `time_off_responsible_approval`
3. Upgrade `time_off_extra_approval`

Hook `post_init` của từng module cập nhật `ir.model.data` (xmlid) nếu đổi tên module cho activity/cron.

## Trạng thái triển khai

- [x] Tài liệu kiến trúc (file này)
- [x] Module `time_off_work_handover` (models phụ, data, security, `models/hr_leave.py` ~2000 dòng)
- [x] Module `time_off_responsible_approval` (models phụ, data, security, `models/hr_leave.py` ~1400 dòng)
- [x] `time_off_extra_approval/models/hr_leave.py` thu còn ~700 dòng (emergency, discuss link, glue `write`/`create`/`action_confirm`, extra approver rules)
- [x] Views/assets handover → `time_off_work_handover`; multi-step/refuse wizard → `time_off_responsible_approval`
- [x] Tách `hr_leave.py` runtime: `time_off_work_handover/models/hr_leave.py` (bàn giao + OdooBot Bàn giao), `time_off_responsible_approval/models/hr_leave.py` (duyệt + OdooBot Duyệt đơn), core glue trong `time_off_extra_approval`
- [ ] Test đầy đủ trên DB staging sau upgrade
- [ ] (Tuỳ chọn) Gỡ cài `time_off_work_handover` nếu công ty không dùng bàn giao

## `hr.leave` gốc Odoo

Custom **không sửa** file `addons/hr_holidays/models/hr_leave.py`. Mọi extension dùng `_inherit = "hr.leave"` trong 3 module trên. Gỡ custom = uninstall 3 module → `hr.leave` trở lại hành vi chuẩn Odoo (mất field/cột custom trên DB nếu không migration).

## Lưu ý

- Không xóa `time_off_extra_approval` — vẫn là module “app” người dùng cài.
- `business_discuss_bots` giữ nguyên; bot Q&A vẫn đọc `hr.leave`.
- Test: gửi đơn nghỉ → DM bàn giao → DM duyệt → approve/refuse.
