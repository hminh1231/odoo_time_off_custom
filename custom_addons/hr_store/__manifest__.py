# -*- coding: utf-8 -*-
{
    'name': 'HR Stores',
    'version': '19.0.1.2.0',
    'category': 'Human Resources',
    'summary': 'Quản lý cửa hàng và gán cửa hàng cho nhân viên',
    'depends': ['hr'],
    'data': [
        'security/ir.model.access.csv',
        'data/hr_store_place_data.xml',
        'views/hr_store_place_views.xml',
        'views/hr_store_views.xml',
        'views/hr_store_menus.xml',
        'views/hr_employee_views.xml',
    ],
    'license': 'LGPL-3',
    'author': 'Custom',
    'installable': True,
    'application': False,
}
