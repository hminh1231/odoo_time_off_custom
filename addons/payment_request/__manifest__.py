# -*- coding: utf-8 -*-
{
    'name': 'Payment Request',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Internal payment requests with approval workflow',
    'depends': ['mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/payment_request_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
