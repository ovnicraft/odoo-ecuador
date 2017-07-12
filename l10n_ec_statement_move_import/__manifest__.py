# -*- coding: utf-8 -*-

{
    'name': 'Account Statement Move Import',
    'version': '10.0',
    'category': 'Accounting',
    'sequence': 14,
    'summary': '',
    'description': """
Account Statement Move Import
=============================
Add a wizard to import moves on bank and cash statements
    """,
    'author': 'Oscar Morocho',
    'website': 'www.ayni.com.ec',
    'license': 'AGPL-3',
    'images': [
    ],
    'depends': [
        'account',
    ],
    'data': [
        'wizard/account_statement_move_import_wizard_view.xml',
        'account_view.xml',
    ],
    'demo': [
    ],
    'test': [
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
