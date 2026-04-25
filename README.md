# Odoo custom: Time Off + HR responsibles + CCCD scan

Modules for **Odoo 19**:

| Module | Mô tả ngắn |
|--------|------------|
| `hr_employee_multi_responsible` | Nhiều HR responsible trên nhân viên |
| `time_off_extra_approval` | Duyệt nghỉ phép bổ sung theo loại nghỉ |
| `hr_job_title_vn` | Chức danh (job title) dạng chọn sẵn theo nhãn phổ biến tại VN |
| `hr_employee_cccd_scan` | Quét CCCD để điền nhanh thông tin nhân viên trên form HR Employee |

## Cài đặt

1. Copy thư mục này vào máy chạy Odoo (hoặc clone repo này).
2. Thêm đường dẫn vào `addons_path` trong `odoo.conf`, ví dụ: `addons_path = ...,/đường/dẫn/custom_addons`
3. Cập nhật Apps và cài module theo nhu cầu:
   - `HR Employee Multiple Responsibles` trước, sau đó `Time Off Extra Approvers`.
   - `HR Job Title (Vietnamese selection)` cài độc lập khi cần.
   - `Employee ID Card Scan (CCCD)` cài độc lập khi cần tính năng scan CCCD trên form nhân viên.

Tag `timeoff-stable-2026-04-05` đánh dấu bản đã kiểm tra trước khi chỉnh sửa thêm.
