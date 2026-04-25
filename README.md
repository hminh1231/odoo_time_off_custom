# Odoo custom: Time Off + HR + Discuss + CCCD

Bộ add-on cho **Odoo 19** (các module đặt cạnh nhau tại thư mục add-ons, ví dụ `custom_addons/`).

| Module | Tên ứng dụng (gần đúng) | Mô tả ngắn |
|--------|-------------------------|------------|
| `hr_employee_multi_responsible` | HR Employee Multiple Responsibles | Nhiều HR responsible trên từng nhân viên. |
| `time_off_extra_approval` | Time Off Extra Approvers | Duyệt nghỉ phép bổ sung theo loại nghỉ (bàn giao, bước duyệt, v.v.). |
| `hr_job_title_vn` | HR Job Title (Vietnamese selection) | Chức danh (job title) chọn sẵn theo nhãn thông dụng tại VN. |
| `hr_employee_cccd_scan` | Employee ID Card Scan (CCCD) | Quét CCCD để điền nhanh thông tin nhân viên trên form HR Employee. |
| `hr_employee_self_only` | HR Employee Self Only Access | **Employees = No:** ẩn tab *Personal* khi xem hồ sơ người khác; vẫn dùng full list / Many2one (bàn giao, tìm kiếm, v.v.). |
| `business_discuss_bots` | Business Discuss Bots | Bot Discuss phục vụ thông báo / tích hợp quy trình nội bộ (phụ thuộc `mail_bot`). |

## Yêu cầu cài theo thứ tự

1. Cài trước: **`hr_employee_multi_responsible`**, sau đó **`time_off_extra_approval`** (extra approval bám theo cấu hình HR).
2. Các module còn lại cài theo nhu cầu; **`hr_employee_self_only`** cần khi tối ưu quyền xem tab Personal cho user không thuộc *Employees*.

## Cài đặt (server)

1. Copy thư mục này lên máy chạy Odoo (hoặc clone [repo](https://github.com/hminh1231/odoo_time_off_custom) — toàn bộ add-on ở **gốc** repo, không nằm dưới tên `custom_addons`).
2. Thêm đường dẫn vào `addons_path` trong `odoo.conf`, ví dụ:  
   `addons_path = ...,/đường/dẫn/custom_addons`  
   (nếu clone GitHub, trỏ tới thư mục chứa trực tiếp các module, ví dụ: `.../odoo_time_off_custom`).
3. Cập nhật Apps, bật chế độ developer nếu cần, cài từng ứng dụng tương ứng ở bảng trên.

## Ghi chú bản ổn định

Tag **`timeoff-stable-2026-04-05`** đánh dấu bản đã kiểm tra trước khi chỉnh sửa thêm.
