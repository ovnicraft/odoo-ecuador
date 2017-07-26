# -*- coding: utf-8 -*-

from itertools import groupby

from odoo import api, models


class ReporteComprobante(models.AbstractModel):

    _name = 'report.l10n_ec_withholding.reporte_move'

    def groupby(self, lines):
        """
        Agrupa lineas por cuenta contable
        """
        glines = []
        for k, g in groupby(lines, key=lambda r: r.account_id):
            debit = 0
            credit = 0
            for i in g:
                debit += i.debit
                credit += i.credit
            glines.append({
                'code': k.code,
                'name': k.name,
                'debit': debit,
                'credit': credit
            })
        return glines

    def group_analytic_lines(self, lines):
        analytic_lines = []
        for line in lines:
            if line.analytic_line_ids.exists():
                analytic_lines.append(line.analytic_line_ids)
        return analytic_lines

    def has_analytics(self, lines):
        for line in lines:
            if line.analytic_line_ids.exists():
                return True
        return False

    @api.model
    def render_html(self, docids, data=None):
        docargs = {
            'doc_ids': docids,
            'doc_model': 'account.move',
            'docs': self.env['account.move'].browse(docids),
            'groupby': self.groupby,
            'group_analytic_lines': self.group_analytic_lines,
            'has_analytics': self.has_analytics
        }
        return self.env['report'].render('l10n_ec_withholding.reporte_move', values=docargs)  # noqa
