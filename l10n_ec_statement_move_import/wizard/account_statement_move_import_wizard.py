# -*- coding: utf-8 -*-

import datetime
import calendar
from odoo import fields, models, api, _
from odoo.exceptions import Warning


class account_statement_move_import_wizard(models.TransientModel):
    _name = "account.statement.move.import.wizard"
    _description = "account_statement_move_import_wizard"

    @api.model
    def _get_statement(self):
        return self.env['account.bank.statement'].browse(
            self._context.get('active_id', False))

    @api.model
    def _default_date_start(self):
        today = datetime.date.today()
        today = today.replace(day=1)
        res = fields.Date.to_string(today)
        return res

    @api.model
    def _default_date_stop(self):
        today = datetime.date.today()
        first, last = calendar.monthrange(today.year, today.month)
        today = today.replace(day=last)
        res = fields.Date.to_string(today)
        return res

    from_date = fields.Date(
        'From Date',
        required=True,
        default=_default_date_start
    )
    to_date = fields.Date(
        'To Date',
        required=True,
        default=_default_date_stop
    )
    statement_id = fields.Many2one(
        'account.bank.statement',
        'Statement',
        default=_get_statement,
        required=True,
        ondelete='cascade',
    )
    journal_id = fields.Many2one(
        'account.journal',
        _('Journal'),
        compute='get_journal',
    )
    journal_account_ids = fields.Many2many(
        'account.account',
        compute='get_accounts',
        string=_('Journal Accounts')
    )
    move_line_ids = fields.Many2many(
        'account.move.line',
        'account_statement_import_move_line_rel',
        'line_id', 'move_line_id',
        'Journal Items',
        domain="[('journal_id', '=', journal_id), "
        "('statement_id', '=', False), "
        "('account_id', 'in', journal_account_ids[0][2])]"
    )

    @api.multi
    @api.depends('statement_id')
    def get_journal(self):
        self.journal_id = self.statement_id.journal_id

    @api.onchange('from_date', 'to_date', 'journal_id')
    def get_move_lines(self):
        move_lines = self.move_line_ids.search([
            ('journal_id', '=', self.journal_id.id),
            ('account_id', 'in', self.journal_account_ids.ids),
            ('statement_id', '=', False),
            ('exclude_on_statements', '=', False),
            ('date', '>=', self.from_date),
            ('date', '<=', self.to_date)]
        )
        self.move_line_ids = move_lines

    @api.multi
    def move_lines(self):
        move_lines = self.move_line_ids.search([
            ('journal_id', '=', self.journal_id.id),
            ('account_id', 'in', self.journal_account_ids.ids),
            ('statement_id', '=', False),
            ('exclude_on_statements', '=', False),
            ('date', '>=', self.from_date),
            ('date', '<=', self.to_date)]
        )
        return move_lines

    @api.multi
    @api.depends('journal_id')
    def get_accounts(self):
        self.journal_account_ids = (
            self.journal_id.default_credit_account_id +
            self.journal_id.default_debit_account_id)

    @api.multi
    def confirm(self):
        statement = self.statement_id
        statement_currency = statement.currency_id
        company_currency = statement.company_id.currency_id
        for line in self.move_lines():
            if line.account_id not in self.journal_account_ids:
                raise Warning(_(
                    'Imported line account must be one of the journals '
                    'defaults, in this case %s') % (
                    ', '.join(self.journal_account_ids.mapped('name'))))

            if line.statement_id:
                raise Warning(_(
                    'Imported line must have "statement_id" == False'))

            line_balance = line.debit - line.credit
            if statement_currency != company_currency:
                if line.currency_id != statement_currency:
                    raise Warning(
                        'Si el diario del extracto es en otra moneda distinta '
                        'a la de la compañía, los apuntes a importar deben '
                        'tener como otra moneda esa misma moneda (%s)' % (
                            statement_currency.name))
                amount = line.amount_currency
                currency_id = False
                amount_currency = False
            else:
                amount = line_balance
                currency_id = line.currency_id.id
                amount_currency = line.amount_currency

            line_vals = {
                'statement_id': statement.id,
                'date': line.date,
                'name': line.name,
                'ref': line.ref,
                'amount': amount,
                'imported': True,
                'imported_line_id': line.id,
                'currency_id': currency_id,
                'amount_currency': amount_currency,
                'partner_id': line.partner_id.id,
                'journal_entry_id': line.move_id.id,
            }
            statement.line_ids.create(line_vals)
            line.write({'statement_id': statement.id})
        return True
