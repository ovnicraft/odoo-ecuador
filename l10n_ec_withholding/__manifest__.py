# -*- coding: utf-8 -*-
# © <2016> <Cristian Salamea>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Retenciones para Ecuador',
    'version': '10.0.1.0.0',
    'category': 'Generic Modules/Accounting',
    'license': 'AGPL-3',
    'depends': [
        'l10n_ec_authorisation',
        'l10n_ec_tax',
        'date_range'
    ],
    'author': 'Cristian Salamea <cristian.salamea@ayni.com.ec>',
    'website': 'http://www.ayni.com.ec',
    'data': [
        'security/ir.model.access.csv',
        'data/account.fiscal.position.csv',
        'data/data.xml',
        'views/report_account_move.xml',
        'views/reports.xml',
        'views/withholding_view.xml',
        'wizard/withholding_wizard.xml'
    ]
}
