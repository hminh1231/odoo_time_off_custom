from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # Regional and ID Information
    mien = fields.Char(string='Miền', groups='hr.group_hr_user')
    id_hrm = fields.Char(string='ID HRM', groups='hr.group_hr_user')

    # Accounting and Attendance Codes
    ma_nv_ke_toan = fields.Char(string='Mã NV kế toán', groups='hr.group_hr_user')
    ma_cham_cong = fields.Char(string='Mã chấm công', groups='hr.group_hr_user')

    # Name without diacritics
    ten_khong_dau = fields.Char(string='Tên không dấu', groups='hr.group_hr_user')

    # Employee Status
    trang_thai_nhan_vien = fields.Selection([
        ('active', 'Đang làm việc'),
        ('probation', 'Thử việc'),
        ('leave', 'Nghỉ phép'),
        ('terminated', 'Đã nghỉ việc'),
    ], string='Trạng thái nhân viên', default='active', groups='hr.group_hr_user')

    # Department Information
    ma_bo_phan = fields.Char(string='Mã bộ phận', groups='hr.group_hr_user')
    ten_bo_phan = fields.Char(string='Tên bộ phận', groups='hr.group_hr_user')
    bp_ke_toan = fields.Char(string='BP Kế toán', groups='hr.group_hr_user')

    # Banking Information
    so_tai_khoan = fields.Char(string='Số tài khoản', groups='hr.group_hr_user')
    chi_nhanh_ngan_hang = fields.Char(string='Chi nhánh NH', groups='hr.group_hr_user')

    # Position Details
    ma_chuc_vu = fields.Char(string='Mã chức vụ', groups='hr.group_hr_user')
    cap_tai = fields.Char(string='Cấp tại', groups='hr.group_hr_user')

    # Additional Address
    dia_chi_tam_tru = fields.Char(string='Địa chỉ tạm trú', groups='hr.group_hr_user')

    # Personal Background
    trinh_do = fields.Selection([
        ('secondary', 'Trung học cơ sở'),
        ('high_school', 'Trung học phổ thông'),
        ('intermediate', 'Trung cấp'),
        ('college', 'Cao đẳng'),
        ('bachelor', 'Đại học'),
        ('master', 'Thạc sĩ'),
        ('doctorate', 'Tiến sĩ'),
    ], string='Trình độ', groups='hr.group_hr_user')
    ton_giao = fields.Char(string='Tôn giáo', groups='hr.group_hr_user')
    dan_toc = fields.Char(string='Dân tộc', groups='hr.group_hr_user')
    nguyen_quan = fields.Char(string='Nguyên quán', groups='hr.group_hr_user')

    # Social Insurance
    so_so_bhxh = fields.Char(string='Số sổ BHXH', groups='hr.group_hr_user')
    ngay_tham_gia_bhxh = fields.Date(string='Ngày tham gia BHXH', groups='hr.group_hr_user')

    # Tax Information
    ma_so_thue = fields.Char(string='Mã số thuế', groups='hr.group_hr_user')

    # Employment Dates
    ngay_vao_lam = fields.Date(string='Ngày vào làm', groups='hr.group_hr_user')
    ngay_nghi_viec = fields.Date(string='Ngày nghỉ việc', groups='hr.group_hr_user')
    ngay_chinh_thuc = fields.Date(string='Ngày chính thức', groups='hr.group_hr_user')

    # Recruitment and Notes
    nguon_tuyen_dung = fields.Char(string='Nguồn tuyển dụng', groups='hr.group_hr_user')
    ghi_chu = fields.Text(string='Ghi chú', groups='hr.group_hr_user')

    # Former Employee Flag
    nhan_vien_cu = fields.Boolean(string='Nhân viên cũ', default=False, groups='hr.group_hr_user')
