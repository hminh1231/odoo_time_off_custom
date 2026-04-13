# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Employee ID Card Scan (CCCD)',
    'version': '19.0.1.16.0',
    'category': 'Human Resources',
    'summary': 'Scan national ID card to fill employee data (UI hook, step 1)',
    'depends': ['hr'],
    'data': [
        'views/hr_employee_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_employee_cccd_scan/static/src/form/form_controller_patch.js',
            'hr_employee_cccd_scan/static/src/id_card_camera/id_card_camera_dialog.scss',
            'hr_employee_cccd_scan/static/src/id_card_camera/id_card_camera_dialog.xml',
            'hr_employee_cccd_scan/static/src/id_card_camera/id_card_camera_dialog.js',
        ],
    },
    'license': 'LGPL-3',
    'author': 'Custom',
    'installable': True,
    'application': False,
}
