# -*- coding:utf-8 -*-
{
    'name': 'Manage Employee Payroll for Ecuador',
    'version': '10.0.0.1.0',
    'category': 'Generic Modules/Human Resources',
    'author': "Cristian Salamea <cristian.salamea@ayni.com.ec>",
    'website': 'http://www.ayni.com.ec',
    'depends': [
        'l10n_ec_hr_contract',
        'hr_payroll_account',
        'hr_attendance'
    ],
    'data': [
        'data/payroll_data.xml',
        'views/hr_payroll_view.xml'
    ]
}
