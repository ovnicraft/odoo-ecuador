# -*- coding: utf-8 -*-
# © <2017> <Jonathan Finlay>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import os
import time
import logging
import itertools

from datetime import datetime
from jinja2 import Environment, FileSystemLoader

from odoo import api, models, fields
from odoo.exceptions import Warning as UserError

from odoo.addons.l10n_ec_einvoice.models import utils
from odoo.addons.l10n_ec_einvoice.xades.sri import DocumentXML
from odoo.addons.l10n_ec_einvoice.xades.xades import Xades


class StockPicking(models.Model):

    _name = 'stock.picking'
    _inherit = ['stock.picking', 'account.edocument']
    _logger = logging.getLogger('account.edocument')

    TEMPLATE = 'erefguide.xml'
    STATES_VALUE = {'draft': [('readonly', False)]}

    carrier_id = fields.Many2one(
        'res.partner',
        'Transportista')
    carrier_plate = fields.Char('Placa')
    max_date = fields.Date('Fecha máxima de entrega')
    reason_id = fields.Many2one('stock.picking.move.reason', 'Motivo de traslado')
    route = fields.Char('Ruta')
    auth_id = fields.Many2one(
        'account.authorisation',
        'Autorización'
    )
    picking_number = fields.Char(
        'Número',
        size=64,
        readonly=True,
        states=STATES_VALUE,
        copy=False
    )

    _sql_constraints = [
        (
            'unique_picking_number',
            'unique(picking_number)',
            u'El número de guía es único.'
        )
    ]

    @api.multi
    def do_authorize_sri(self):
        for obj in self:
            if not obj.auth_id.is_electronic:
                return True
            obj.action_generate_document()

    @api.onchange('picking_number')
    @api.constrains('picking_number')
    def _onchange_name(self):
        if not len(self.picking_number) == 15 or not self.picking_number.isdigit():
            raise UserError(u'Nro incorrecto. Debe ser de 15 dígitos.')
        if not self.auth_id.is_valid_number(int(self.picking_number[-9:])):
            raise UserError('Nro no pertenece a la secuencia.')

    @api.multi
    def action_number(self):
        for picking in self:
            sequence = picking.auth_id.sequence_id
            if picking.picking_type_id.code != 'incoming' and not picking.picking_number:
                number = picking.auth_id.serie_entidad + picking.auth_id.serie_emision + sequence.next_by_id()
            picking.write({'picking_number': number})
        return True

    def do_transfer(self):
        for p in self:
            p.action_number()
        super(StockPicking, self).do_transfer()

    def check_date(self, date_invoice):
        """
        Validar que el envío del comprobante electrónico
        se realice dentro de las 24 horas posteriores a su emisión
        """
        LIMIT_TO_SEND = 5
        MESSAGE_TIME_LIMIT = u' '.join([
            u'Los comprobantes electrónicos deben',
            u'enviarse con máximo 24h desde su emisión.']
        )
        dt = datetime.strptime(date_invoice, '%Y-%m-%d %H:%M:%S')
        days = (datetime.now() - dt).days
        if days > LIMIT_TO_SEND:
            raise UserError(MESSAGE_TIME_LIMIT)

    def _info_guia(self, erefguide):
        """
        """
        def fix_date(date):
            date = date.split(' ')[0]
            d = time.strftime('%d/%m/%Y',
                              time.strptime(date, '%Y-%m-%d'))
            return d

        company = erefguide.company_id
        carrier = erefguide.carrier_id
        infoGuiaRemision = {
            'dirEstablecimiento': erefguide.picking_type_id.warehouse_id.partner_id.street2,
            'dirPartida': company.street2,
            'razonSocialTransportista': carrier.name,  # noqa
            'tipoIdentificacionTransportista': utils.tipoIdentificacion[carrier.type_identifier],
            'rucTransportista': carrier.identifier,
            'obligadoContabilidad': 'SI',
            'fechaIniTransporte': fix_date(erefguide.min_date),
            'fechaFinTransporte': fix_date(erefguide.max_date) if erefguide.max_date else fix_date(erefguide.min_date),
            'placa': erefguide.carrier_plate,
        }
        if company.company_registry:
            infoGuiaRemision.update({'contribuyenteEspecial': company.company_registry})
        else:
            raise UserError('No ha determinado si es contribuyente especial.')
        return infoGuiaRemision

    def _destinatarios(self, erefguide):
        """
        """
        def fix_chars(code):
            special = [
                [u'%', ' '],
                [u'º', ' '],
                [u'Ñ', 'N'],
                [u'ñ', 'n'],
                [u'\n', ' ']
            ]
            for f, r in special:
                code = code.replace(f, r)
            return code

        def fix_date(date):
            d = time.strftime('%d/%m/%Y',
                              time.strptime(date, '%Y-%m-%d'))
            return d

        destinatarios = []
        partner = erefguide.partner_id
        invoice = self.env['account.invoice'].search([('picking_id','=',self.id)])
        inv_number = '{0}-{1}-{2}'.format(invoice.invoice_number[:3], invoice.invoice_number[3:6], invoice.invoice_number[6:])
        #for line in erefguide.move_lines:
        destinatario = {
            'identificacionDestinatario': partner.identifier,
            'razonSocialDestinatario': partner.name,
            'dirDestinatario': partner.street2,
            'motivoTraslado': erefguide.reason_id.name if erefguide.reason_id else '',
            'ruta': erefguide.route,
            'codDocSustento': invoice.auth_inv_id.type_id.code,
            'numDocSustento': inv_number,
            'numAutDocSustento': invoice.numero_autorizacion,
            'fechaEmisionDocSustento': fix_date(invoice.date_invoice)
        }
        detalles = []
        for line in erefguide.move_lines:
            detalle = {
                'codigoInterno': line.product_id.name,
                'codigoAdicional': line.product_id.default_code,
                'descripcion': line.product_id.description_picking,
                'cantidad': line.product_qty
            }
            detalles.append(detalle)
        destinatario.update({'detalles': detalles})
        destinatarios.append(destinatario)
        return {'destinatarios': destinatarios}

    def render_document(self, erefguide, access_key, emission_code):
        tmpl_path = os.path.join(os.path.dirname(__file__), 'templates')
        env = Environment(loader=FileSystemLoader(tmpl_path))
        erefguide_tmpl = env.get_template(self.TEMPLATE)
        data = {}
        data.update(self._info_tributaria(erefguide, access_key, emission_code))
        data.update(self._info_guia(erefguide))
        destinatarios = self._destinatarios(erefguide)
        data.update(destinatarios)
        erefguide = erefguide_tmpl.render(data)
        return erefguide

    def render_authorized_eerefguide(self, autorizacion):
        tmpl_path = os.path.join(os.path.dirname(__file__), 'templates')
        env = Environment(loader=FileSystemLoader(tmpl_path))
        erefguide_tmpl = env.get_template('authorized_erefguide.xml')
        auth_xml = {
            'estado': autorizacion.estado,
            'numeroAutorizacion': autorizacion.numeroAutorizacion,
            'ambiente': autorizacion.ambiente,
            'fechaAutorizacion': str(autorizacion.fechaAutorizacion.strftime("%d/%m/%Y %H:%M:%S")),  # noqa
            'comprobante': autorizacion.comprobante
        }
        auth_refguide = erefguide_tmpl.render(auth_xml)
        return auth_refguide

    @api.multi
    def action_generate_document(self):
        """
        Metodo de generacion de guia de remision electronica
        TODO: usar celery para enviar a cola de tareas
        la generacion de la factura y envio de email
        """
        for obj in self:
            self.check_date(obj.min_date)
            self.check_before_sent()
            access_key, emission_code = self._get_codes(name='stock.picking')
            erefguide = self.render_document(obj, access_key, emission_code)
            inv_xml = DocumentXML(erefguide, 'stock_picking')
            inv_xml.validate_xml()
            xades = Xades()
            file_pk12 = obj.company_id.electronic_signature
            password = obj.company_id.password_electronic_signature
            signed_document = xades.sign(erefguide, file_pk12, password)
            ok, errores = inv_xml.send_receipt(signed_document)
            if not ok:
                raise UserError(errores)
            auth, m = inv_xml.request_authorization(access_key)
            if not auth:
                msg = ' '.join(list(itertools.chain(*m)))
                raise UserError(msg)
            auth_erefguide = self.render_authorized_eerefguide(auth)
            self.update_document(auth, [access_key, emission_code])
            attach = self.add_attachment(auth_erefguide, auth)
            message = """
            DOCUMENTO ELECTRONICO GENERADO <br><br>
            CLAVE DE ACCESO: %s <br>
            NUMERO DE AUTORIZACION %s <br>
            FECHA AUTORIZACION: %s <br>
            ESTADO DE AUTORIZACION: %s <br>
            AMBIENTE: %s <br>
            """ % (
                self.clave_acceso,
                self.numero_autorizacion,
                self.fecha_autorizacion,
                self.estado_autorizacion,
                self.ambiente
            )
            self.message_post(body=message)
            self.send_document(
                attachments=[a.id for a in attach],
                tmpl='l10n_ec_einvoice_picking.email_template_erefguide'
            )

    @api.multi
    def erefguide_print(self):
        return self.env['report'].get_action(
            self,
            'l10n_ec_einvoice_picking.report_erefguide'
        )


class RefGuideReason(models.Model):
    """Motivos del traslado"""
    _name = 'stock.picking.move.reason'
    _description = __doc__

    name = fields.Char('Razón')
