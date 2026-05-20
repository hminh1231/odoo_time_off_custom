{
    "name": "Time Off Work Handover",
    "version": "19.0.1.0.1",
    "category": "Human Resources",
    "summary": "Work handover workflow for time off requests",
    "depends": ["hr_holidays", "business_discuss_bots", "time_off_extra_approval"],
    "post_init_hook": "post_init_hook",
    "data": [
        "data/mail_activity_type_data.xml",
        "security/handover_security.xml",
        "views/hr_leave_form_handover_views.xml",
        "views/hr_leave_handover_refuse_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "time_off_work_handover/static/src/scss/handover_replacement.scss",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
