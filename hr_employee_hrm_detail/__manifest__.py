{
    'name': 'HR Employee HRM Detail',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Employees',
    'summary': 'Add HRM detail fields to employee Personal tab',
    'description': """
        HR Employee HRM Detail
        ======================
        This module adds comprehensive HRM fields to the employee form:
        - Regional information (Miền, ID HRM)
        - Accounting codes (Mã NV kế toán, Mã chấm công)
        - Department details (Mã bộ phận, Tên bộ phận, BP Kế toán)
        - Banking information (Số tài khoản, Chi nhánh NH)
        - Position details (Mã chức vụ, Cấp tại)
        - Personal information (Trình độ, Tôn giáo, Dân tộc, Nguyên quán)
        - Social insurance (Số sổ BHXH, Ngày tham gia BHXH)
        - Employment dates (Ngày vào làm, Ngày nghỉ việc, Ngày chính thức)
        - Additional info (Nguồn tuyển dụng, Ghi chú, Nhân viên cũ)
    """,
    'depends': ['hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_employee_views.xml',
    ],
    'license': 'LGPL-3',
    'author': 'Custom',
    'installable': True,
    'application': False,
    'auto_install': False,
}
