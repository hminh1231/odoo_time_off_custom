# -*- coding: utf-8 -*-
{
    "name": "Time Off Calendar — Status Colors",
    "version": "1.0.0",
    "category": "Human Resources",
    "summary": "Color-code time off calendar events and legend by approval status.",
    "depends": ["hr_holidays"],
    "data": [
        "views/hr_leave_report_calendar_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "assets": {
        "web.assets_backend": [
            "timeoff_calendar_status_colors/static/src/scss/*.scss",
            ("remove", "timeoff_calendar_status_colors/static/src/scss/*.dark.scss"),
        ],
        "web.assets_web_dark": [
            "timeoff_calendar_status_colors/static/src/scss/*.dark.scss",
        ],
    },
}
