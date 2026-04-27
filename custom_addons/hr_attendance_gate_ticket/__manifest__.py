{
    'name': 'HR Attendance Gate Ticket',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'summary': 'Extend HR Attendance with gate ticket functionality',
    'depends': ['hr_attendance'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_attendance_views.xml',
        'report/gate_ticket_report.xml',
    ],
    'license': 'LGPL-3',
    'author': 'Custom',
    'installable': True,
    'application': False,
    'auto_install': False,
}
