# -*- coding: utf-8 -*-

import base64

from odoo import http
from odoo.http import request

from odoo.addons.website_portal.controllers.main import website_account


class WebsiteEdocument(website_account):

    @http.route(['/my', '/my/home'], type='http', auth="user", website=True)
    def account(self, **kw):
        """ Add invoices and withholding documents to main account page """
        response = super(WebsiteEdocument, self).account(**kw)
        partner = request.env.user.partner_id
        Invoice = request.env['account.invoice']
        invoice_count = Invoice.search_count([
            ('type', 'in', ['out_invoice', 'out_refund']),
            ('partner_id', '=', partner.id),
            ('state', 'in', ['open', 'paid', 'cancel']),
            ('autorizado_sri', '=', True)
        ])
        response.qcontext.update({
            'invoice_count': invoice_count
        })
        return response

    @http.route(['/my/einvoices',
                 '/my/einvoices/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_my_documents(self, page=1, date_begin=None, date_end=None, **kw):  # noqa
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        Invoice = request.env['account.invoice']
        domain = [
            ('type', 'in', ['out_invoice', 'out_refund']),
            ('partner_id', '=', partner.id),
            ('state', 'in', ['open', 'paid', 'cancel']),
            ('autorizado_sri', '=', True)
        ]

        archive_groups = self._get_archive_groups('account.invoice', domain)
        if date_begin and date_end:
            domain += [('date_invoice', '>=', date_begin),
                       ('date_invoice', '<=', date_end)]
        invoice_count = Invoice.search_count(domain)
        pager = request.website.pager(
            url='/my/einvoices',
            url_args={'date_begin': date_begin, 'date_end': date_end},
            total=invoice_count,
            page=page,
            step=self._items_per_page
        )
        invoices = Invoice.search(domain, limit=self._items_per_page, offset=pager['offset'])  # noqa
        values.update({
            'date': date_begin,
            'invoices': invoices,
            'page_name': 'invoice',
            'pager': pager,
            'archive_groups': archive_groups,
            'default_url': '/my/einvoices'
        })
        return request.render(
            'l10n_ec_edocument_portal.portal_my_einvoices',
            values
        )

    @http.route(['/my/einvoices/pdf/<int:invoice>/'],
                type='http', auth="user", website=True)
    def print_invoice(self, invoice, **kw):
        xml_attach = request.env['ir.attachment'].search([
            ('res_model', '=', 'account.invoice'),
            ('mimetype', '=', 'application/pdf'),
            ('res_id', '=', invoice)
        ])
        content_base64 = base64.b64decode(xml_attach.datas)
        headers = [
            ('Content-Length', len(content_base64)),
            ('Content-type', 'application/pdf'),
            ('Content-Disposition', 'attachment; filename=%s' % xml_attach.datas_fname)  # noqa
        ]
        response = request.make_response(content_base64, headers)
        return response

    @http.route(
        ['/my/einvoices/xml/<int:invoice_id>/'],
        type='http', auth='user', website=True
    )
    def get_xml(self, invoice_id, **kw):
        xml_attach = request.env['ir.attachment'].search([
            ('res_model', '=', 'account.invoice'),
            ('mimetype', '=', 'text/xml'),
            ('res_id', '=', invoice_id)
        ])
        content_base64 = base64.b64decode(xml_attach.datas)
        headers = [
            ('Content-Length', len(content_base64)),
            ('Content-type', 'text/xml'),
            ('Content-Disposition', 'attachment; filename=%s' % xml_attach.datas_fname)  # noqa
        ]
        response = request.make_response(content_base64, headers)
        return response
