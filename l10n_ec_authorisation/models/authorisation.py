# -*- coding: utf-8 -*-
# © <2016> <Cristian Salamea>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import time
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError, RedirectWarning


class AccountAtsDoc(models.Model):
    _name = 'account.ats.doc'
    _description = 'Tipos Comprobantes Autorizados'

    code = fields.Char('Código', size=2, required=True)
    name = fields.Char('Tipo Comprobante', size=64, required=True)


class AccountAtsSustento(models.Model):
    _name = 'account.ats.sustento'
    _description = 'Sustento del Comprobante'

    @api.multi
    @api.depends('code', 'type')
    def name_get(self):
        res = []
        for record in self:
            name = '%s - %s' % (record.code, record.type)
            res.append((record.id, name))
        return res

    _rec_name = 'type'

    code = fields.Char('Código', size=2, required=True)
    type = fields.Char('Tipo de Sustento', size=128, required=True)


class AccountAuthorisation(models.Model):

    _name = 'account.authorisation'
    _order = 'expiration_date desc'

    @api.multi
    @api.depends('type_id', 'num_start', 'num_end')
    def name_get(self):
        res = []
        for record in self:
            name = u'%s (%s-%s)' % (
                record.type_id.code,
                record.num_start,
                record.num_end
            )
            res.append((record.id, name))
        return res

    @api.one
    @api.depends('expiration_date')
    def _compute_active(self):
        """
        Check the due_date to give the value is_active field
        """
        if self.is_electronic:
            self.is_active = True
        else:
            if not self.expiration_date:
                return
            now = datetime.strptime(time.strftime("%Y-%m-%d"), '%Y-%m-%d')
            due_date = datetime.strptime(self.expiration_date, '%Y-%m-%d')
            self.is_active = now < due_date

    def _get_type(self):
        return self._context.get('type', 'in_invoice')  # pylint: disable=E1101

    def _get_in_type(self):
        return self._context.get('in_type', 'externo')

    def _get_partner(self):
        if self._context.get('in_type') == 'externo':
            return
        partner = self.env.user.company_id.partner_id
        if self._context.get('partner_id'):
            partner = self._context.get('partner_id')
        return partner

    @api.model
    @api.returns('self', lambda value: value.id)
    def create(self, values):
        domain = [
            ('partner_id', '=', values['partner_id']),
            ('type_id', '=', values['type_id']),
            ('serie_entidad', '=', values['serie_entidad']),
            ('serie_emision', '=', values['serie_emision']),
            ('is_active', '=', True)
        ]
        res = self.search(domain)
        if res:
            MSG = u'Ya existe una autorización activa para este tipo de documento.'
            raise ValidationError(MSG)

        partner_id = self.env.user.company_id.partner_id.id
        if values['partner_id'] == partner_id:
            typ = self.env['account.ats.doc'].browse(values['type_id'])
            name_type = '{0}_{1}'.format(values['name'], values['type_id'])
            sequence_data = {
                'code': typ.code == '07' and 'account.retention' or 'account.invoice',  # noqa
                'name': name_type,
                'padding': 9,
                'number_next': values['num_start'],
                }
            seq = self.env['ir.sequence'].create(sequence_data)
            values.update({'sequence_id': seq.id})
        return super(AccountAuthorisation, self).create(values)

    @api.multi
    def unlink(self):
        inv = self.env['account.invoice']
        res = inv.search([('auth_inv_id', '=', self.id)])
        if res:
            raise UserError(
                'Esta autorización esta relacionada a un documento.'
            )
        return super(AccountAuthorisation, self).unlink()

    name = fields.Char('Num. de Autorización', size=128)
    serie_entidad = fields.Char('Serie Entidad', size=3, required=True)
    serie_emision = fields.Char('Serie Emision', size=3, required=True)
    num_start = fields.Integer('Desde')
    num_end = fields.Integer('Hasta')
    is_electronic = fields.Boolean('Documento Electrónico ?')
    expiration_date = fields.Date('Fecha de Vencimiento')
    is_active = fields.Boolean(
        compute='_compute_active',
        string='Activo',
        store=True,
        default=True
    )
    in_type = fields.Selection(
        [('interno', 'Internas'),
         ('externo', 'Externas')],
        string='Tipo Interno',
        readonly=True,
        change_default=True,
        default=_get_in_type
    )
    type_id = fields.Many2one(
        'account.ats.doc',
        'Tipo de Comprobante',
        required=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        'Empresa',
        required=True,
        default=_get_partner
    )
    sequence_id = fields.Many2one(
        'ir.sequence',
        'Secuencia',
        help='Secuencia Alfanumerica para el documento, se debe registrar cuando pertenece a la compañia',  # noqa
        ondelete='cascade'
    )

    _sql_constraints = [
        ('number_unique',
         'unique(partner_id,expiration_date,type_id,serie_entidad)',
         u'La relación de autorización, serie entidad, serie emisor y tipo, debe ser única.'),  # noqa
        ]

    def is_valid_number(self, number):
        """
        Metodo que verifica si @number esta en el rango
        de [@num_start,@num_end]
        """
        if self.is_electronic and self.num_start <= number:
            return True
        if self.num_start <= number <= self.num_end:
            return True
        return False


class ResPartner(models.Model):
    _inherit = 'res.partner'

    authorisation_ids = fields.One2many(
        'account.authorisation',
        'partner_id',
        'Autorizaciones'
    )

    @api.multi
    def get_authorisation(self, type_document):
        map_type = {
            'out_invoice': '18',
            'in_invoice': '01',
            'out_refund': '04',
            'in_refund': '05',
            'liq_purchase': '03',
            'ret_in_invoice': '07',
            'stock_picking': '06',
        }
        code = map_type[type_document]
        for a in self.authorisation_ids:
            if a.is_active and a.type_id.code == code:
                return a
        return False


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    auth_out_invoice_id = fields.Many2one(
        'account.authorisation',
        'Secuencia Facturas'
    )
    auth_out_refund_id = fields.Many2one(
        'account.authorisation',
        'Secuencia Notas de Credito'
    )
    auth_retention_id = fields.Many2one(
        'account.authorisation',
        'Para Retenciones'
    )


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    _DOCUMENTOS_EMISION = ['out_invoice', 'liq_purchase', 'out_refund']

    @api.onchange('journal_id', 'auth_inv_id')
    def _onchange_journal_id(self):
        super(AccountInvoice, self)._onchange_journal_id()
        if self.journal_id and self.type in self._DOCUMENTOS_EMISION:
            if self.type == 'out_invoice':
                self.auth_inv_id = self.journal_id.auth_out_invoice_id
            elif self.type == 'out_refund':
                self.auth_inv_id = self.journal_id.auth_out_refund_id
            self.auth_number = not self.auth_inv_id.is_electronic and self.auth_inv_id.name  # noqa
            number = '{0}'.format(
                str(self.auth_inv_id.sequence_id.number_next_actual).zfill(9)
            )
            self.reference = number

    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_id(self):
        """
        Redefinicion de metodo para obtener:
        numero de autorizacion
        numero de documento
        El campo auth_inv_id representa la autorizacion para
        emitir el documento.
        """
        res = super(AccountInvoice, self)._onchange_partner_id()
        if not self.partner_id:
            return res
        if self.type not in self._DOCUMENTOS_EMISION:
            auth = self.partner_id.get_authorisation(self.type)
            if not auth:
                action = self.env.ref('l10n_ec_authorisation.action_account_authoriz_out_form')
                raise RedirectWarning('No ha configurado una autorización en el Partner', action, 'Configurar')
            self.auth_inv_id = auth.id

    @api.one
    @api.depends(
        'state',
        'reference'
    )
    def _compute_invoice_number(self):
        """
        Calcula el numero de factura segun el
        establecimiento seleccionado
        """
        if self.reference:
            self.invoice_number = '{0}{1}{2}'.format(
                self.auth_inv_id.serie_entidad,
                self.auth_inv_id.serie_emision,
                self.reference
            )
        else:
            self.invoice_number = '*'

    invoice_number = fields.Char(
        compute='_compute_invoice_number',
        string='Nro. Documento',
        store=True,
        readonly=True,
        copy=False
    )
    internal_inv_number = fields.Char('Numero Interno', copy=False)
    auth_inv_id = fields.Many2one(
        'account.authorisation',
        string='Establecimiento',
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='Autorizacion para documento',
        copy=False
    )
    auth_number = fields.Char('Autorización')
    sustento_id = fields.Many2one(
        'account.ats.sustento',
        string='Sustento del Comprobante'
    )

    _sql_constraints = [
        (
            'unique_invoice_number',
            'unique(reference,type,partner_id,state)',
            u'El número de factura es único.'
        )
    ]

    @api.onchange('auth_inv_id')
    def _onchange_auth(self):
        if self.auth_inv_id and not self.auth_inv_id.is_electronic:
            self.auth_number = self.auth_inv_id.name

    @api.onchange('reference')
    def _onchange_ref(self):
        # TODO: agregar validacion numerica a reference
        if self.reference:
            if len(self.reference) > 9:
                raise UserError(
                    u'Debe ingresar máximo 9 dígitos.'
                )
            self.reference = self.reference.zfill(9)
            auth = self.auth_inv_id
            if not auth.is_electronic and not auth.is_valid_number(int(self.reference)):
                return {
                    'value': {
                        'reference': ''
                    },
                    'warning': {
                        'title': 'Error',
                        'message': u'Número no coincide con la autorización ingresada.'  # noqa
                    }
                }

    @api.constrains('auth_number')
    def check_reference(self):
        """
        Metodo que verifica la longitud de la autorizacion
        10: documento fisico
        35: factura electronica modo online
        49: factura electronica modo offline
        """
        if self.type not in ['in_invoice', 'liq_purchase']:
            return
        if self.auth_number and len(self.auth_number) not in [10, 37, 49]:
            raise UserError(
                u'Debe ingresar 10, 37 o 49 dígitos según el documento.'
            )

    @api.multi
    def action_number(self):
        # TODO: ver donde incluir el metodo de numeracion
        for inv in self:
            if inv.type not in ['out_invoice', 'liq_purchase', 'out_refund']:
                return
            number = inv.internal_inv_number
            if not inv.auth_inv_id:
                # asegura la autorizacion en el objeto
                inv._onchange_partner_id()
            if not number:
                sequence = inv.auth_inv_id.sequence_id
                number = sequence.next_by_id()
                inv.write({'reference': number, 'internal_inv_number': number})

    @api.multi
    def action_invoice_open(self):
        # lots of duplicate calls to action_invoice_open,
        # so we remove those already open
        # redefined for numbering document
        to_open_invoices = self.filtered(lambda inv: inv.state != 'open')
        if to_open_invoices.filtered(lambda inv: inv.state not in ['proforma2', 'draft']):  # noqa
            raise UserError(_("Invoice must be in draft or Pro-forma state in order to validate it."))  # noqa
        to_open_invoices.action_date_assign()
        to_open_invoices.action_move_create()
        to_open_invoices.action_number()
        return to_open_invoices.invoice_validate()
