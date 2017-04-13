# -*- coding: utf-8 -*-
{
    'name': 'Portal para Documentos Electronicos',
    'version': '10.0.0.1.0',
    'author': 'Cristian Salamea',
    'category': 'Localization',
    'license': 'AGPL-3',
    'complexity': 'normal',
    'data': [
        'security/ir.model.access.csv',
        'views/index_view.xml'
    ],
    'depends': [
        'portal',
        'website_portal',
        'l10n_ec_einvoice',
    ]
}
