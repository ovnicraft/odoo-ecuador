# -*- coding: utf-8 -*-

import os
import time
import logging
import itertools

from jinja2 import Environment, FileSystemLoader

from openerp import fields, models, api
from openerp.exceptions import Warning as UserError

from . import utils
from ..xades.sri import DocumentXML
from ..xades.xades import Xades


class AccountWithdrawing(models.Model):

    _name = 'account.retention'
    _inherit = ['account.retention', 'account.edocument']
    _logger = logging.getLogger(_name)

    def get_secuencial(self):
        return getattr(self, 'name')[6:15]

    def _info_withdrawing(self, withdrawing):
        """
        """
        # generar infoTributaria
        company = withdrawing.company_id
        partner = withdrawing.invoice_id.partner_id
        now = fields.Date.from_string(withdrawing.date)
        periodo = "%s/%s" % (
            str(now.month).zfill(2),
            now.year
        )
        infoCompRetencion = {
            'fechaEmision': time.strftime('%d/%m/%Y', time.strptime(withdrawing.date, '%Y-%m-%d')),  # noqa
            'dirEstablecimiento': company.street,
            'obligadoContabilidad': 'SI',
            'tipoIdentificacionSujetoRetenido': utils.tipoIdentificacion[partner.type_identifier],  # noqa
            'razonSocialSujetoRetenido': partner.name,
            'identificacionSujetoRetenido': partner.identifier,
            'periodoFiscal': periodo,
            }
        if company.company_registry:
            infoCompRetencion.update({'contribuyenteEspecial': company.company_registry})  # noqa
        return infoCompRetencion

    def _impuestos(self, retention):
        """
        """
        def get_codigo_retencion(linea):
            if linea.tax_id.tax_group_id.code in ['ret_vat_b', 'ret_vat_srv']:
                return utils.tabla21[line.tax_id.percent_report]
            else:
                code = linea.tax_id.description
                return code

        impuestos = []
        for line in retention.tax_ids:
            if line.tax_id.tax_group_id.code in ['ret_vat_b', 'ret_vat_srv']:
                base = retention.invoice_id.amount_tax
            else:
                base = line.base
            impuesto = {
                'codigo': utils.tabla20[line.tax_id.tax_group_id.code],
                'codigoRetencion': get_codigo_retencion(line),
                'baseImponible': '%.2f' % (base),
                'porcentajeRetener': str(line.tax_id.percent_report),
                'valorRetenido': '%.2f' % (abs(line.amount)),
                'codDocSustento': retention.invoice_id.sustento_id.code,
                'numDocSustento': retention.invoice_id.invoice_number,
                'fechaEmisionDocSustento': time.strftime('%d/%m/%Y', time.strptime(retention.invoice_id.date_invoice, '%Y-%m-%d'))  # noqa
            }
            impuestos.append(impuesto)
        return {'impuestos': impuestos}

    def render_document(self, document, access_key, emission_code):
        tmpl_path = os.path.join(os.path.dirname(__file__), 'templates')
        env = Environment(loader=FileSystemLoader(tmpl_path))
        ewithdrawing_tmpl = env.get_template('ewithdrawing.xml')
        data = {}
        data.update(self._info_tributaria(document, access_key, emission_code))
        data.update(self._info_withdrawing(document))
        data.update(self._impuestos(document))
        edocument = ewithdrawing_tmpl.render(data)
        self._logger.debug(edocument)
        return edocument

    def render_authorized_document(self, autorizacion):
        tmpl_path = os.path.join(os.path.dirname(__file__), 'templates')
        env = Environment(loader=FileSystemLoader(tmpl_path))
        edocument_tmpl = env.get_template('authorized_withdrawing.xml')
        auth_xml = {
            'estado': autorizacion.estado,
            'numeroAutorizacion': autorizacion.numeroAutorizacion,
            'ambiente': autorizacion.ambiente,
            'fechaAutorizacion': str(autorizacion.fechaAutorizacion.strftime("%d/%m/%Y %H:%M:%S")),  # noqa
            'comprobante': autorizacion.comprobante
        }
        auth_withdrawing = edocument_tmpl.render(auth_xml)
        return auth_withdrawing

    @api.multi
    def action_generate_document(self):
        """
        """
        for obj in self:
            self.check_date(obj.date)
            self.check_before_sent()
            access_key, emission_code = self._get_codes(name='account.retention')
            ewithdrawing = self.render_document(obj, access_key, emission_code)
            self._logger.debug(ewithdrawing)
            inv_xml = DocumentXML(ewithdrawing, 'withdrawing')
            inv_xml.validate_xml()
            xades = Xades()
            file_pk12 = obj.company_id.electronic_signature
            password = obj.company_id.password_electronic_signature
            signed_document = xades.sign(ewithdrawing, file_pk12, password)
            ok, errores = inv_xml.send_receipt(signed_document)
            if not ok:
                raise UserError(errores)
            auth, m = inv_xml.request_authorization(access_key)
            if not auth:
                msg = ' '.join(list(itertools.chain(*m)))
                raise UserError(msg)
            auth_document = self.render_authorized_document(auth)
            self.update_document(auth, [access_key, emission_code])
            attach = self.add_attachment(auth_document, auth)
            return True

    @api.multi
    def retention_print(self):
        return self.env['report'].get_action(
            self,
            'l10n_ec_einvoice.report_eretention'
        )

    @api.multi
    def action_send_eretention(self):
        '''
        This function send electronic retention generated
        '''
        if self.partner_id.email:
            attach = self.env['ir.attachment']
            attachment_ids = attach.search(
                [('res_model', '=', 'account.retention'), ('res_id', '=', self.id)])
            if attachment_ids:
                self.attachment_count = len(attachment_ids)
            self.send_document(
                attachments=[a.id for a in attachment_ids],
                tmpl='l10n_ec_einvoice.email_template_eretention'
            )
        else:
            raise UserError('Ingresar correo electrónico del proveedor')


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def action_generate_eretention(self):
        for obj in self:
            if not obj.journal_id.auth_retention_id.is_electronic:
                return True
            obj.retention_id.action_generate_document()

    @api.multi
    def action_withholding_create(self):
        super(AccountInvoice, self).action_withholding_create()
        for obj in self:
            if obj.type in ['in_invoice', 'liq_purchase']:
                obj.action_generate_eretention()


class AccountTax(models.Model):
    _inherit = 'account.tax'

    code_tax = fields.Char(
        'Código de Impuesto',
        size=64,
        readonly=False,
    )