{
    "name": "Time Off Extra Approvers (Demo)",
    "version": "19.0.6.1.39",
    "category": "Human Resources",
    "summary": "Allow extra officers/offices to approve time off by leave type",
    "depends": ["hr_holidays", "hr_employee_multi_responsible", "hr_job_title_vn"],
    "post_init_hook": "post_init_hook",
    "data": [
        "data/mail_activity_type_data.xml",
        "security/extra_approvers_security.xml",
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "views/hr_leave_type_views.xml",
        "views/hr_leave_search_views.xml",
        "views/hr_leave_form_handover_views.xml",
        "views/hr_leave_handover_refuse_wizard_views.xml",
        "views/hr_leave_kanban_extra_approval.xml",
        "views/hr_leave_list_extra_approval.xml",
        "views/hr_leave_multi_step_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "time_off_extra_approval/static/src/js/many2one_save_on_change_field.js",
            "time_off_extra_approval/static/src/js/timeoff_cancel_dialog_fix.js",
            "time_off_extra_approval/static/src/js/emergency_leave_form_controller.js",
        ],
    },
    "installable": True,
    "application": True,
    "license": "LGPL-3"
}
