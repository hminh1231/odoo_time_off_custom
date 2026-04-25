{
    "name": "HR Employee Self Only Access",
    "version": "19.0.1.1.3",
    "category": "Human Resources",
    "summary": "Employees=No: hide Personal tab on others; full employee list for handover and search",
    "depends": ["hr"],
    "data": [
        "security/hr_employee_privilege_groups.xml",
        "views/hr_employee_views.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
    "assets": {
        "web.assets_backend": [
            "hr_employee_self_only/static/src/js/res_user_group_ids_employees_no_order.js",
            "hr_employee_self_only/static/src/js/hr_employee_form_privacy_readonly.js",
            "hr_employee_self_only/static/src/scss/hr_employee_form_privacy_readonly.scss",
        ],
    },
}
