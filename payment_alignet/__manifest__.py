# -*- coding: utf-8 -*-

{
    'name': 'VPOS Alignet Payment Acquirer',
    'category': 'Accounting',
    'summary': 'Payment Acquirer: VPOS Alignet Implementation',
    'version': '1.0',
    'description': """VPOS Alignet Payment Acquirer""",
    'depends': ['payment'],
    'website': 'www.prisehub.com',
    'author': 'PriseHub Co. Ltd.',
    'data': [
        'views/payment_views.xml',
        'views/payment_alignet_templates.xml',
        'data/payment_acquirer_data.xml',
    ],
    'installable': True,
}
