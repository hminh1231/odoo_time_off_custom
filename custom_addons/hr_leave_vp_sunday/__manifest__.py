# -*- coding: utf-8 -*-
{
    "name": "Time Off — VP Sunday Rules",
    "version": "19.0.1.0.0",
    "category": "Human Resources",
    "summary": "Block or exclude Sundays from time off for VP department employees",
    "description": """
        For employees with department code VP (ma_bo_phan from hr_employee_hrm_detail):

        * **Block** (default): Sundays cannot be selected on the time-off calendar and are rejected on save.
        * **Exclude from count**: Sundays may appear in the range but are not counted in duration.
    """,
    "depends": ["hr_holidays", "hr_employee_hrm_detail"],
    "data": [
        "data/ir_config_parameter_data.xml",
        "views/res_config_settings_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
