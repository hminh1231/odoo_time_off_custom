# Odoo custom: Time Off + HR responsibles

Modules for **Odoo 19**:

| Module | Mô tả ngắn |
|--------|------------|
| `hr_employee_multi_responsible` | Nhiều HR responsible trên nhân viên |
| `time_off_extra_approval` | Duyệt nghỉ phép bổ sung theo loại nghỉ |
| `hr_job_title_vn` | Chức danh (job title) dạng chọn sẵn theo nhãn phổ biến tại VN |

## Cài đặt

1. Copy thư mục này vào máy chạy Odoo (hoặc clone repo này).
2. Thêm đường dẫn vào `addons_path` trong `odoo.conf`, ví dụ: `addons_path = ...,/đường/dẫn/custom_addons`
3. Cập nhật Apps → cài `HR Employee Multiple Responsibles` trước, sau đó `Time Off Extra Approvers`. Module `HR Job Title (Vietnamese selection)` cài độc lập khi cần.

Tag `timeoff-stable-2026-04-05` đánh dấu bản đã kiểm tra trước khi chỉnh sửa thêm.
