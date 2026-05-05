# Odoo custom: Time Off + HR + Discuss + CCCD

Bộ add-on cho **Odoo 19**. Toàn bộ module nằm trong thư mục **`custom_addons/`** của repo (clone xong trỏ `addons_path` vào đúng thư mục đó).

| Module | Tên ứng dụng (gần đúng) | Mô tả ngắn |
|--------|-------------------------|------------|
| `hr_employee_multi_responsible` | HR Employee Multiple Responsibles | Nhiều HR responsible trên từng nhân viên (nền tảng cho luồng duyệt nghỉ). |
| `hr_job_title_vn` | HR Job Title (Vietnamese selection) | Chức danh (job title) chọn sẵn theo nhãn thông dụng tại VN. |
| `business_discuss_bots` | Business Discuss Bots | Bot Discuss cho thông báo / quy trình nội bộ (phụ thuộc `mail_bot`; được `time_off_extra_approval` dùng cho tin nhắn bot). |
| `time_off_extra_approval` | Time Off Extra Approvers | Duyệt nghỉ phép bổ sung theo loại nghỉ (bàn giao, nhiều bước duyệt, người phụ trách HR, v.v.). |
| `hr_employee_hrm_detail` | HR Employee HRM Detail | Bổ sung các field HRM chi tiết trên tab Personal của nhân viên. |
| `hr_employee_gate_ticket` | GateTicket | Ứng dụng phiếu cổng / gate ticket gắn HR Employee & chấm công. |
| `hr_employee_cccd_scan` | Employee ID Card Scan (CCCD) | Quét CCCD để điền nhanh thông tin nhân viên trên form HR Employee. |
| `hr_employee_self_only` | HR Employee Self Only Access | **Employees = No:** ẩn tab *Personal* khi xem hồ sơ người khác; vẫn dùng full list / Many2one (bàn giao, tìm kiếm, v.v.). |
| `vn_language_switch` | Vietnamese Language Switch | Chuyển ngôn ngữ theo user (EN/VI) qua menu & cài đặt (phụ thuộc `base`, `web`). |

## Yêu cầu cài theo thứ tự

Module **`time_off_extra_approval`** phụ thuộc manifest vào: **`hr_holidays`**, **`hr_employee_multi_responsible`**, **`hr_job_title_vn`**, **`business_discuss_bots`**.

1. Cài theo thứ tự (sau khi đã có các app Odoo chuẩn tương ứng):  
   **`hr_employee_multi_responsible`** → **`hr_job_title_vn`** → **`business_discuss_bots`** → **`time_off_extra_approval`**.
2. Các module còn lại cài theo nhu cầu.
3. **`hr_employee_self_only`**: dùng khi muốn tối ưu quyền xem tab Personal cho user không thuộc nhóm *Employees*.
4. **`vn_language_switch`**: tùy chọn, bật khi cần chuyển EN/VI rõ ràng trên giao diện.

## Cài đặt (server)

1. Clone repo [odoo_time_off_custom](https://github.com/hminh1231/odoo_time_off_custom) (hoặc copy thư mục project lên máy chạy Odoo).
2. Thêm đường dẫn tới thư mục **`custom_addons`** vào `addons_path` trong `odoo.conf`, ví dụ:  
   `addons_path = ...,/đường/dẫn/odoo_time_off_custom/custom_addons`
3. Khởi động Odoo, cập nhật Apps, bật chế độ developer nếu cần, cài từng ứng dụng theo bảng và thứ tự ở trên.

## Ghi chú bản ổn định

Tag **`timeoff-stable-2026-04-05`** đánh dấu bản đã kiểm tra tại thời điểm đó; các commit sau có thể thêm module hoặc thay đổi hành vi — nên test sau mỗi lần `git pull`.

## Deploy-ready cho công ty (pull về chạy)

Repo có thư mục `deploy/` để đồng bộ môi trường giữa máy dev và máy công ty.

### Cách dùng nhanh

1. Copy file mẫu:
   - `deploy/.env.example` -> `deploy/.env`
   - `deploy/odoo.conf.example` -> `deploy/odoo.conf`
2. Chỉnh thông số DB trong 2 file trên cho đúng môi trường công ty.
3. Chạy stack:
   - `docker compose -f deploy/docker-compose.yml up -d`
4. Sau mỗi lần `git pull`, chạy cập nhật module:
   - Linux/macOS: `sh scripts/post_deploy.sh`
   - Windows PowerShell: `.\scripts\post_deploy.ps1`

Xem hướng dẫn chi tiết tại `deploy/README.md`.
