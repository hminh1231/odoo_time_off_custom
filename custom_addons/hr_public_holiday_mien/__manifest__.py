# -*- coding: utf-8 -*-
{
    "name": "Ngày lễ theo miền",
    "version": "19.0.1.1.4",
    "category": "Human Resources/Time Off",
    "summary": "Phân ngày lễ Văn Phòng và Cửa Hàng theo miền nhân viên",
    "description": """
        Cho phép cấu hình ngày lễ riêng cho Văn Phòng (miền VP) và Cửa Hàng
        (miền Bắc, Nam, ĐTT). Lịch nghỉ phép của mọi Miền hiển thị ngày lễ VP
        (ngày lễ chung). Tab Cửa Hàng dùng cấu hình riêng, không trộn vào lịch NV.

        Nhân viên cửa hàng (miền Bắc, Nam, ĐTT) làm việc cả tuần (7 ngày):
        ngày lễ VP vẫn hiển thị tham khảo nhưng không trừ vào số ngày phép.
    """,
    "depends": [
        "hr_holidays",
        "hr_employee_hrm_detail",
    ],
    "data": [
        "data/resource_calendar_store_data.xml",
        "data/sync_store_calendar_data.xml",
        "views/resource_calendar_leaves_views.xml",
    ],
    "post_init_hook": "post_init_hook",
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
