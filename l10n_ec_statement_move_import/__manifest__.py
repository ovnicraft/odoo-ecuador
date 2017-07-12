# -*- coding: utf-8 -*-

{
    'name': 'Account Statement Move Import',
    'category': 'Accounting',
    'summary': '',
    'description': """
Account Statement Move Import
=============================
Add a wizard to import moves on bank and cash statements
    """,
    'author': 'Oscar Morocho',
    'website': 'www.ayni.com.ec',
    'license': 'AGPL-3',
    'depends': [
        'account',
    ],
    'data': [
        'wizard/account_statement_move_import_wizard_view.xml',
        'view/account_view.xml',
    ],
    'installable': True,
}