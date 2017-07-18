# -*- coding: utf-8 -*-
{
    'name': 'Electronic Documents for Ecuador',
    'version': '10.0.1.0.0',
    'author': 'Jonathan Finlay',
    'category': 'Localization',
    'license': 'AGPL-3',
    'complexity': 'normal',
    'data': [
        'data/account.ats.doc.csv',
        'data/stock.picking.move.reason.csv',
        'security/ir.model.access.csv',
        'views/report_erefguide.xml',
        'views/edocument_layouts.xml',
        'views/stock_picking_view.xml',
        'edi/erefguide_edi.xml',
        'wizard/picking_invoice_create_wizard.xml',
        'views/account_view.xml',
    ],
    'depends': [
        'account',
        'stock',
        'l10n_ec_einvoice'
    ],
    'installable': True,
}
