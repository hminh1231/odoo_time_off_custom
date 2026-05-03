{
    'name': 'GateTicket',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'summary': 'Standalone HR Employee Gate Ticket app',
    'depends': ['base', 'mail', 'hr', 'hr_attendance'],
    'data': [
        'security/hr_employee_gate_ticket_security.xml',
        'security/ir.model.access.csv',
        'data/gate_ticket_sequence.xml',
        'report/gate_ticket_report.xml',
        'views/hr_employee_gate_ticket_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_employee_gate_ticket/static/src/js/gate_ticket_form.js',
        ],
    },
    'license': 'LGPL-3',
    'author': 'Custom',
    'installable': True,
    'application': True,
    'auto_install': False,
}
