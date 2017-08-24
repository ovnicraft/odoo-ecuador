# -*- coding: utf-8 -*-

import datetime
import cStringIO
import base64
import xlwt
from pytz import timezone
from odoo import models, fields, api, _
from odoo.exceptions import Warning
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
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


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.multi
    def button_cancel(self):
        if self._context.get('cancel_from_statement_line', False):
            return super(AccountMove, self).button_cancel()

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
            return super(AccountMove, self).button_cancel()


class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'

    @api.multi
    def button_cancel(self):
        return super(AccountBankStatement, self.with_context(
            cancel_from_statement=True)).button_cancel()

    @api.multi
    def bank_reconciliation_report(self):
        journal_ids = self.env['account.journal']
        move_line_ids = self.env['account.move.line']
        filename = 'BankReconciliation/%s.xls' % (self.date)
        workbook = xlwt.Workbook(encoding='utf-8', style_compression=2)
        worksheet = workbook.add_sheet('Moves')
        style = xlwt.easyxf('font:height 200, bold True, name Arial; align: horiz center, vert center;borders: top medium,right medium,bottom medium,left medium')
        style0 = xlwt.easyxf('font: name Times New Roman, color-index black, bold on')
        for obj in self:
            worksheet.write_merge(0, 2, 0, 11, str(obj.company_id.name) + u'\n Bank Reconciliation\n' + str(datetime.datetime.now(timezone('America/Guayaquil'))), style)
            fila = 4
            columna = 0
            worksheet.write(fila, columna, obj.name, style0)
            fila = fila + 1
            worksheet.write(fila, 0, 'Fecha: ' + obj.date, style0)
            worksheet.write(fila, 6, 'Usuario: ' + obj.user_id.partner_id.name, style0)
            fila = fila + 1
            worksheet.write(fila, 0, 'Saldo Inicial: ' + str(obj.balance_start), style0)
            worksheet.write(fila, 6, 'Saldo Final: ' + str(obj.balance_end_real), style0)
            fila = fila + 1
            worksheet.write(fila, 0, 'Banco: ' + obj.journal_id.default_debit_account_id.name, style0)
            fila = fila + 1
            worksheet.write(fila, 0, 'Fecha', style0)
            worksheet.write(fila, 1, u'Número', style0)
            worksheet.write(fila, 3, 'Referencia', style0)
            worksheet.write(fila, 6, 'Empresa', style0)
            worksheet.write(fila, 10, 'Debe', style0)
            worksheet.write(fila, 11, 'Haber', style0)
            fila = fila + 1
            td = 0
            tc = 0
            for lids in obj.line_ids:
                worksheet.write(fila, 0, lids.date)
                worksheet.write(fila, 1, lids.name)
                worksheet.write(fila, 3, lids.ref)
                worksheet.write(fila, 6, lids.partner_id.name)
                if lids.amount > 0:
                    worksheet.write(fila, 10, lids.amount)
                    td = td + lids.amount
                else:
                    worksheet.write(fila, 11, abs(lids.amount))
                    tc = tc + abs(lids.amount)
                fila = fila + 1
            worksheet.write(fila, 8, 'Total:', style0)
            worksheet.write(fila, 10, td, style0)
            worksheet.write(fila, 11, tc, style0)
            totalc = td - tc
            fila = fila + 1
            worksheet.write(fila, 8, 'Total Conciliado: ' + str(totalc), style0)
            fila = fila + 2
            worksheet.write(fila, 0, 'Transacciones no Conciliadas', style0)
            account_journal_ids = journal_ids.search([
                ('default_debit_account_id', '=', obj.journal_id.default_debit_account_id.id),
                ('default_credit_account_id', '=', obj.journal_id.default_credit_account_id.id)]
            )
            fila = fila + 1
            worksheet.write(fila, 0, 'Fecha', style0)
            worksheet.write(fila, 1, u'Número', style0)
            worksheet.write(fila, 3, 'Referencia', style0)
            worksheet.write(fila, 6, 'Empresa', style0)
            worksheet.write(fila, 10, 'Debe', style0)
            worksheet.write(fila, 11, 'Haber', style0)
            fila = fila + 1
            tdnc = 0
            tcnc = 0
            for journal_line in account_journal_ids:
                move_lines = move_line_ids.search([
                    ('journal_id', '=', journal_line.id),
                    ('account_id', '=', journal_line.default_debit_account_id.id),
                    ('statement_id', '=', False),
                    ('exclude_on_statements', '=', False),
                    ('date', '<=', obj.date)])
                for move_line in move_lines:
                    worksheet.write(fila, 0, move_line.date)
                    worksheet.write(fila, 1, move_line.name)
                    worksheet.write(fila, 3, move_line.ref)
                    worksheet.write(fila, 6, move_line.partner_id.name)
                    worksheet.write(fila, 10, move_line.debit)
                    worksheet.write(fila, 11, move_line.credit)
                    tdnc = tdnc + move_line.debit
                    tcnc = tcnc + move_line.credit
                    fila = fila + 1
            tnc = tdnc - tcnc
            worksheet.write(fila, 9, 'Total No conciliado:' + str(tnc), style0)
            fila = fila + 1
            worksheet.write(fila, 9, 'Total Bancos:' + str(obj.balance_start + totalc + tnc), style0)
            fp = cStringIO.StringIO()
            workbook.save(fp)
            dataxls = {
                'excel_file': base64.encodestring(fp.getvalue()),
                'file_name': filename
            }
            export_id = self.env['excel.extended'].create(dataxls)
            fp.close()

        return{
            'view_mode': 'form',
            'res_id': export_id.id,
            'res_model': 'excel.extended',
            'view_type': 'form',
            'type': 'ir.actions.act_window',
            'context': None,
            'target': 'new',
        }


class InventoryExcelExtended(models.Model):
    _name = "excel.extended"
    excel_file = fields.Binary('Reporte Excel')
    file_name = fields.Char('Excel File', size=64)


class AccountBankStatementLine(models.Model):
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
            return super(AccountBankStatementLine, self.filtered(
                lambda r: not r.imported_line_id and not r.imported)).cancel()
        for line in self:
            if line.imported_line_id or line.imported:
                raise Warning(_(
                    'You can not cancel line "%s" as it has been imported with'
                    ' "Import Journal Items" wizard, you can delete it '
                    'instead') % ('%s - %s' % (line.name, line.ref or '')))
        return super(AccountBankStatementLine, self.with_context(
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
        return super(AccountBankStatementLine, self).unlink()
