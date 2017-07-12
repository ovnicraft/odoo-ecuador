# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
from openerp.exceptions import Warning
from odoo.exceptions import UserError


class account_move_line(models.Model):
    _inherit = 'account.move.line'

    exclude_on_statements = fields.Boolean(
        'Exclude on Statements',
        help='Exclude this move line suggestion on statements',
    )

    @api.multi
    def _update_check(self):
        move_ids = set()
        for line in self:
            err_msg = _('Move name (id): %s (%s)') % (line.move_id.name, str(line.move_id.id))
            if line.reconciled and not (line.debit == 0 and line.credit == 0):
                raise UserError(_('You cannot do this modification on a reconciled entry. You can just change some non legal fields or you must unreconcile first.\n%s.') % err_msg)
            if line.move_id.id not in move_ids:
                move_ids.add(line.move_id.id)
            self.env['account.move'].browse(list(move_ids))._check_lock_date()


class account_move(models.Model):
    _inherit = 'account.move'

    @api.multi
    def button_cancel(self):
        if self._context.get('cancel_from_statement_line', False):
            return super(account_move, self).button_cancel()

        statement_lines = self.env['account.bank.statement.line']
        statement_lines = statement_lines.sudo().search([
            ('imported_line_id', 'in', self.ids)]
        )
        if statement_lines:
            raise Warning(_(
                "You can not cancel an Accounting Entry that is linked "
                "to a statement. You should cancel or delete lines from "
                "statement first. Related Statements: '%s'") % (
                    ', '.join(statement_lines.mapped('statement_id.name'))))
        else:
            return super(account_move, self).button_cancel()


class account_bank_statement(models.Model):
    _inherit = 'account.bank.statement'

    @api.multi
    def button_cancel(self):
        return super(account_bank_statement, self.with_context(
            cancel_from_statement=True)).button_cancel()


class account_bank_statement_line(models.Model):
    _inherit = 'account.bank.statement.line'

    imported_line_id = fields.Many2one(
        'account.move.line',
        'Imported Move Line',
        readonly=True,
        help='Imported lines are the ones imported by the '
        '"Import Journal Items" wizard. They have some special behaviour, '
        'for eg. you can not cancel them from here',
    )

    @api.multi
    def cancel(self):
        if self._context.get('cancel_from_statement', False):
            return super(account_bank_statement_line, self.filtered(
                lambda r: not r.imported_line_id and not r.imported)).cancel()
        for line in self:
            if line.imported_line_id or line.imported:
                raise Warning(_(
                    'You can not cancel line "%s" as it has been imported with'
                    ' "Import Journal Items" wizard, you can delete it '
                    'instead') % ('%s - %s' % (line.name, line.ref or '')))
        return super(account_bank_statement_line, self.with_context(
            cancel_from_statement_line=True)).cancel()

    @api.multi
    def unlink(self):
        for line in self:
            if line.imported_line_id:
                line.imported_line_id.statement_id = False
                line.journal_entry_id = False
            elif line.imported:
                line.journal_entry_id.line_id.write({'statement_id': False})
                line.journal_entry_id = False
        return super(account_bank_statement_line, self).unlink()
