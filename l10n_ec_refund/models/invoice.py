# -*- coding: utf-8 -*-
# © <2016> <Cristian Salamea>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.model
    def _prepare_refund(self, invoice, date_invoice=None, date=None, description=None, journal_id=None):  # noqa
        vals = super(AccountInvoice, self)._prepare_refund(invoice, date_invoice, date, description, journal_id)  # noqa
        vals.update({'origin': invoice.invoice_number})
        return vals

    @api.model
    def _refund_cleanup_lines(self, lines):
        """ Convert records to dict of values suitable for one2many line creation

            :param recordset lines: records to convert
            :return: list of command tuple for one2many line creation [(0, 0, dict of valueis), ...]
        Redefinido para crear una sola linea para nota de credito
        """
        result = []
        for line in lines:
            values = {
                'name': 'DEVOLUCION POR NOTA DE CREDITO',
                'account_id': line.account_id.id,
                'price_unit': 0.00
            }
            result.append((0, 0, values))
            break
        return result


class AccountInvoiceRefund(models.TransientModel):

    _inherit = 'account.invoice.refund'

    @api.model
    def _get_reason(self):
        context = dict(self._context or {})
        active_id = context.get('active_id', False)
        if not active_id:
            return ''
        inv = self.env['account.invoice'].browse(active_id)
        return inv.invoice_number

    description = fields.Char(default=_get_reason)
