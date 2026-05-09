# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "HR Managed Departments (Giám đốc)",
    "version": "19.0.1.0.6",
    "category": "Human Resources",
    "summary": "Phòng ban quản lý trên hồ sơ NV (từ Manager trên Phòng ban); hiện khi chức danh là giám đốc",
    "depends": ["hr"],
    "data": [
        "views/hr_department_views.xml",
        "views/hr_employee_views.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
