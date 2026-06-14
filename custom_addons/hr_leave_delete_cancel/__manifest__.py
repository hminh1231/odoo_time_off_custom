# -*- coding: utf-8 -*-
{
    "name": "Time Off Delete / Cancel Permission",
    "version": "19.0.1.0.5",
    "category": "Human Resources",
    "summary": "Restrict deleting and cancelling employee time off to explicitly allowed users",
    "depends": [
        "hr_holidays",
        "time_off_extra_approval",
        "time_off_work_handover",
    ],
    "data": [
        "security/hr_leave_delete_cancel_security.xml",
        "views/hr_leave_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
