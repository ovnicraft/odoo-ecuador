# -*- coding: utf-8 -*-
# © <2016> <Cristian Salamea>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


import logging

from odoo import (
    api,
    models
)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.multi
    def print_move(self):
        # Método para imprimir comprobante contable
        move = self.env['account.move'].search([('name', '=', self.move_name)], limit=1)
        return self.env['report'].get_action(
            move,
            'l10n_ec_withholding.reporte_move'
        )
