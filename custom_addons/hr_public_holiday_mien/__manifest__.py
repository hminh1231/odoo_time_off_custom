# -*- coding: utf-8 -*-
{
    "name": "Ngày lễ theo miền",
    "version": "19.0.1.0.0",
    "category": "Human Resources/Time Off",
    "summary": "Phân ngày lễ Văn Phòng và Cửa Hàng theo miền nhân viên",
    "description": """
        Cho phép cấu hình ngày lễ riêng cho Văn Phòng (miền VP) và Cửa Hàng
        (miền Bắc, Nam, ĐTT). Nhân viên chỉ thấy ngày lễ thuộc miền của mình.
    """,
    "depends": [
        "hr_holidays",
        "hr_employee_hrm_detail",
    ],
    "data": [
        "views/resource_calendar_leaves_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "hr_public_holiday_mien/static/src/public_holiday_mien_list/public_holiday_mien_list.scss",
            "hr_public_holiday_mien/static/src/public_holiday_mien_list/public_holiday_mien_list.js",
            "hr_public_holiday_mien/static/src/public_holiday_mien_list/public_holiday_mien_list.xml",
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
