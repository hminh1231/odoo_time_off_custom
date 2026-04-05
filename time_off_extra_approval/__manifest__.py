{
    "name": "Time Off Extra Approvers (Demo)",
    "version": "19.0.6.0.8",
    "category": "Human Resources",
    "summary": "Allow extra officers/offices to approve time off by leave type",
    "depends": ["hr_holidays", "hr_employee_multi_responsible"],
    "post_init_hook": "hooks.post_init_hook",
    "data": [
        "security/extra_approvers_security.xml",
        "security/ir.model.access.csv",
        "views/hr_leave_type_views.xml",
        "views/hr_leave_search_views.xml",
        "views/hr_leave_multi_step_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "time_off_extra_approval/static/src/js/many2one_save_on_change_field.js",
        ],
    },
    "installable": True,
    "application": True,
    "license": "LGPL-3"
}

