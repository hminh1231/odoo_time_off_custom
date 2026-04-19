{
    "name": "HR Employee Self Only Access",
    "version": "19.0.1.0.5",
    "category": "Human Resources",
    "summary": "Restrict internal users to read only their own employee profile",
    "depends": ["hr"],
    "data": [
        "security/hr_employee_privilege_groups.xml",
        "security/hr_employee_self_only_rules.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
    "assets": {
        "web.assets_backend": [
            "hr_employee_self_only/static/src/js/res_user_group_ids_employees_no_order.js",
        ],
    },
}
