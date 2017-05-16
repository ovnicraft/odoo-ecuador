# -*- coding: utf-8 -*-
# © <2016> <Cristian Novillo>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Imprimir Reporte Pagos y Cobros',
    'version': '10.0.1.0.0',
    'category': 'Generic Modules/Accounting',
    'license': 'AGPL-3',
    'depends': [
        'l10n_ec_withholding',
    ],
    'author': 'Cristian Novillo <cristian.novillo@ayni.com.ec>',
    'website': 'http://www.ayni.com.ec',
    'data': [
        'views/payment_printing_view.xml',
        'views/report_payment.xml',
        'views/reports.xml'
    ]
}
