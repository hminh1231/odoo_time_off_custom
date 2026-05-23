# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Time Off Matrix Excel Export",
    "version": "19.0.1.0.11",
    "category": "Human Resources/Time Off",
    "summary": "Export time off as department matrix sheet (HRM layout)",
    "depends": ["hr_holidays", "web", "hr_employee_hrm_detail"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/hr_leave_matrix_export_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "hr_leave_matrix_export/static/src/matrix_export/export_all_matrix_patch.js",
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
