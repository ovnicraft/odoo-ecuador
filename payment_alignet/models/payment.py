# coding: utf-8

import random
from datetime import datetime
import hashlib
import hmac
import logging
import time
import urlparse

from odoo import api, fields, models
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.addons.payment_authorize.controllers.main import AuthorizeController
from odoo.tools.float_utils import float_compare
from odoo.tools.safe_eval import safe_eval

try:
    from alignetpy import alignetpy
except ImportError:
    raise ImportError('Please install alignetpy from: https://github.com/codeadict/alignetpy')


_logger = logging.getLogger(__name__)


class PaymentAcquirerAlignet(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(selection_add=[('alignet', 'VPOS Alignet')])
    acquirer_ref_id = fields.Selection(
        [('8', '8')],
        string='ID Adquiriente',
        default='8',
        readonly=True
    )
    idcommerce = fields.Char('ID Commerce Asignado')
    publickey_sign = fields.Text('Llave publica para Firma')
    publickey_crypt = fields.Text('Llave publica para Cifrado')
    vector = fields.Char('Vector de Inicialización', default='/')

    def _get_alignet_urls(self, environment):
        """ VPOS Alignet URLs """
        if environment == 'prod':
            return {'alignet_form_url': 'https://vpayment.verifika.com/VPOS/MM/transactionStart20.do'}
        else:
            return {'alignet_form_url': 'https://test2.alignetsac.com/VPOS/MM/transactionStart20.do'}

    @api.multi
    def generate_vector(self):
        import os
        rb = os.urandom(8)
        rand_hex = rb.encode('hex')
        self.vector = rand_hex.upper()

    def alignet_vpos(self, values):
        publickey = b"""
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDTJt+hUZiShEKFfs7DShsXCkoq
TEjv0SFkTM04qHyHFU90Da8Ep1F0gI2SFpCkLmQtsXKOrLrQTF0100dL/gDQlLt0
Ut8kM/PRLEM5thMPqtPq6G1GTjqmcsPzUUL18+tYwN3xFi4XBog4Hdv0ml1SRkVO
DRr1jPeilfsiFwiO8wIDAQAB"""
        sig_privatekey = b"""
MIICXQIBAAKBgQC2JnUI5brAK4Yi382WWwarvAcObFUUNXPAX2wT3WgbNdEPnm3y
+B8qtcG+d7TiIFN0KDbLJ3uASzDwgl22K2k6pclvl24PlN2iUtFK5vZ7Y8Kn3BLr
ms7qGJEiiZNS1m4PiYJM5CUWmLtKewnkOCBCOdTY3xxVgaP7iyTTwjoN7wIDAQAV
AoGAPxJtjrQ9wncflIUuHQftzQIzk3fVM563rtS10IdZcPaDzQUi0YlZJ07zPbEP
FQZQ4103NR61djFZSzs78ap+WelXNDwWyDVU7WmwYo6hB7RTJ6VxY7FzR5W2potx
qTMqvmfFq4mmk3h+bJy8bSR7rbsoHm+Lvh0/Kqj/QnvKHj0CQQDQ0kJe+Rn7/fi6
DmZZA6bEhzColMj9n+Z7bhD91Przqki2JpJW7h9+VL0N425SfgDiqMqLfiS+MeqJ
Lgz8mVTPAkEA302acHEaAPkiV+o0us1mwbsZdznccCeAuFyZvlJ3wW3U4mDAAHYY
aQkM9OrRdFIkGsOptT+toU1WWP3GaIo84QJBALSAHrTNmiQH4lx+QQ99LPuZKPhH
V/dk6Oh6V1PwNtAUmPJDdlvImXKLK5ThAbzbSRL813P0bQQqnYX0/k3EyvkCQQDQ
V8k5AZHBBa8bKeZolVFwjxAnF/aKHzmt1YIlmMgmRwrEqWQs9ofNG9QkShIKki+e
ZrB+I6ZzDMrTCQGovHUdAkAH4m7nTJPypY8ENCRsuL/OkDhz1iaeO3Y6WO5OKz49
rKAjdOTAi9O2TzZn3EssbNmHg+XnytlXPPxF8rhdYTYC"""

        vector = self.generate_vector()
        al = alignetpy.Alignet()
        return al.vpos_send(values, publickey, sig_privatekey, vector)

    @api.multi
    def alignet_form_generate_values(self, values):
        self.ensure_one()
        alignet_values = dict()
        temp_alignet_values = {
            'acquirerId': self.acquirer_ref_id,
            'commerceId': self.idcommerce,
            'purchaseCurrencyCode': 'USD',
            'purchaseOperationNumber': values.get('reference') or '',
            'purchaseAmount': str(values['amount']),
            'billingAddress': values.get('billing_partner_address'),
            'billingCity': values.get('billing_partner_city'),
            'billingState': values.get('billing_partner_state') and values['billing_partner_state'].code or '',
            'billingCountry': values.get('billing_partner_country') and values.get('billing_partner_country').name or '',
            'billingEMail': values.get('billing_partner_email'),
            'billingZIP': values.get('billing_partner_zip'),
            'billingFirstName': values.get('billing_partner_first_name'),
            'billingLastName': values.get('billing_partner_last_name'),
            'billingPhone': values.get('billing_partner_phone'),
            'shippingAddress': values.get('partner_address'),
            'shippingCity': values.get('partner_city'),
            'shippingCountry': values.get('partner_country') and values.get('partner_country').name or '',
            'shippingEMail': values.get('partner_email'),
            'shippingZIP': values.get('partner_zip'),
            'shippingFirstName': values.get('partner_first_name'),
            'shippingLastName': values.get('partner_last_name'),
            'shippingPhone': values.get('partner_phone'),
            'shippingState': values.get('partner_state') and values['partner_state'].code or '',
            'reserved1': '0.00',  # BI
            'reserved2': '0.00'  # IVA
        }
        alignet_values.update(temp_alignet_values)
        alignet_values.update(self.alignet_vpos(alignet_values))
        print alignet_values
        return alignet_values

    @api.multi
    def alignet_get_form_action_url(self):
        self.ensure_one()
        return self._get_alignet_urls(self.environment)['alignet_form_url']

    @api.model
    def alignet_s2s_form_process(self, data):
        values = {
            'cc_number': data.get('cc_number'),
            'cc_holder_name': data.get('cc_holder_name'),
            'cc_expiry': data.get('cc_expiry'),
            'cc_cvc': data.get('cc_cvc'),
            'cc_brand': data.get('cc_brand'),
            'acquirer_id': int(data.get('acquirer_id')),
            'partner_id': int(data.get('partner_id'))
        }
        PaymentMethod = self.env['payment.token'].sudo().create(values)
        return PaymentMethod.id

    @api.multi
    def alignet_s2s_form_validate(self, data):
        error = dict()
        mandatory_fields = ["cc_number", "cc_cvc", "cc_holder_name", "cc_expiry", "cc_brand"]
        # Validation
        for field_name in mandatory_fields:
            if not data.get(field_name):
                error[field_name] = 'missing'
        if data['cc_expiry'] and datetime.now().strftime('%y%M') > datetime.strptime(data['cc_expiry'], '%M / %y').strftime('%y%M'):
            return False
        return False if error else True


class TxAuthorize(models.Model):
    _inherit = 'payment.transaction'

    _authorize_valid_tx_status = 1
    _authorize_pending_tx_status = 4
    _authorize_cancel_tx_status = 2

    # --------------------------------------------------
    # FORM RELATED METHODS
    # --------------------------------------------------

    @api.model
    def create(self, vals):
        # The reference is used in the Authorize form to fill a field (invoiceNumber) which is
        # limited to 20 characters. We truncate the reference now, since it will be reused at
        # payment validation to find back the transaction.
        if 'reference' in vals and 'acquirer_id' in vals:
            acquier = self.env['payment.acquirer'].browse(vals['acquirer_id'])
            if acquier.provider == 'authorize':
                vals['reference'] = vals.get('reference', '')[:20]
        return super(TxAuthorize, self).create(vals)

    @api.model
    def _authorize_form_get_tx_from_data(self, data):
        """ Given a data dict coming from authorize, verify it and find the related
        transaction record. """
        reference, trans_id, fingerprint = data.get('x_invoice_num'), data.get('x_trans_id'), data.get('x_MD5_Hash')
        if not reference or not trans_id or not fingerprint:
            error_msg = 'Authorize: received data with missing reference (%s) or trans_id (%s) or fingerprint (%s)' % (reference, trans_id, fingerprint)
            _logger.info(error_msg)
            raise ValidationError(error_msg)
        tx = self.search([('reference', '=', reference)])
        if not tx or len(tx) > 1:
            error_msg = 'Authorize: received data for reference %s' % (reference)
            if not tx:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'
            _logger.info(error_msg)
            raise ValidationError(error_msg)
        return tx[0]

    @api.multi
    def _authorize_form_get_invalid_parameters(self, data):
        invalid_parameters = []

        if self.acquirer_reference and data.get('x_trans_id') != self.acquirer_reference:
            invalid_parameters.append(('Transaction Id', data.get('x_trans_id'), self.acquirer_reference))
        # check what is buyed
        if float_compare(float(data.get('x_amount', '0.0')), self.amount, 2) != 0:
            invalid_parameters.append(('Amount', data.get('x_amount'), '%.2f' % self.amount))
        return invalid_parameters

    @api.multi
    def _authorize_form_validate(self, data):
        if self.state == 'done':
            _logger.warning('Authorize: trying to validate an already validated tx (ref %s)' % self.reference)
            return True
        status_code = int(data.get('x_response_code', '0'))
        if status_code == self._authorize_valid_tx_status:
            if data.get('x_type').lower() in ['auth_capture', 'prior_auth_capture']:
                self.write({
                    'state': 'done',
                    'acquirer_reference': data.get('x_trans_id'),
                    'date_validate': fields.Datetime.now(),
                })
            elif data.get('x_type').lower() in ['auth_only']:
                self.write({
                    'state': 'authorized',
                    'acquirer_reference': data.get('x_trans_id'),
                })
            if self.partner_id and not self.payment_token_id and \
               (self.type == 'form_save' or self.acquirer_id.save_token == 'always'):
                transaction = AuthorizeAPI(self.acquirer_id)
                res = transaction.create_customer_profile_from_tx(self.partner_id, self.acquirer_reference)
                token_id = self.env['payment.token'].create({
                    'authorize_profile': res.get('profile_id'),
                    'name': res.get('name'),
                    'acquirer_ref': res.get('payment_profile_id'),
                    'acquirer_id': self.acquirer_id.id,
                    'partner_id': self.partner_id.id,
                })
                self.payment_token_id = token_id
            return True
        elif status_code == self._authorize_pending_tx_status:
            self.write({
                'state': 'pending',
                'acquirer_reference': data.get('x_trans_id'),
            })
            return True
        elif status_code == self._authorize_cancel_tx_status:
            self.write({
                'state': 'cancel',
                'acquirer_reference': data.get('x_trans_id'),
            })
            return True
        else:
            error = data.get('x_response_reason_text')
            _logger.info(error)
            self.write({
                'state': 'error',
                'state_message': error,
                'acquirer_reference': data.get('x_trans_id'),
            })
            return False

    @api.multi
    def authorize_s2s_do_transaction(self, **data):
        self.ensure_one()
        transaction = AuthorizeAPI(self.acquirer_id)
        if self.acquirer_id.auto_confirm != "authorize":
            res = transaction.auth_and_capture(self.payment_token_id, self.amount, self.reference)
        else:
            res = transaction.authorize(self.payment_token_id, self.amount, self.reference)
        return self._authorize_s2s_validate_tree(res)

    @api.multi
    def authorize_s2s_capture_transaction(self):
        self.ensure_one()
        transaction = AuthorizeAPI(self.acquirer_id)
        tree = transaction.capture(self.acquirer_reference, self.amount)
        return self._authorize_s2s_validate_tree(tree)

    @api.multi
    def authorize_s2s_void_transaction(self):
        self.ensure_one()
        transaction = AuthorizeAPI(self.acquirer_id)
        tree = transaction.void(self.acquirer_reference)
        return self._authorize_s2s_validate_tree(tree)

    @api.multi
    def _authorize_s2s_validate_tree(self, tree):
        return self._authorize_s2s_validate(tree)

    @api.multi
    def _authorize_s2s_validate(self, tree):
        self.ensure_one()
        if self.state == 'done':
            _logger.warning('Authorize: trying to validate an already validated tx (ref %s)' % self.reference)
            return True
        status_code = int(tree.get('x_response_code', '0'))
        if status_code == self._authorize_valid_tx_status:
            if tree.get('x_type').lower() in ['auth_capture', 'prior_auth_capture']:
                init_state = self.state
                self.write({
                    'state': 'done',
                    'acquirer_reference': tree.get('x_trans_id'),
                    'date_validate': fields.Datetime.now(),
                })
                if self.callback_eval and init_state != 'authorized':
                    safe_eval(self.callback_eval, {'self': self})
            if tree.get('x_type').lower() == 'auth_only':
                self.write({
                    'state': 'authorized',
                    'acquirer_reference': tree.get('x_trans_id'),
                })
                if self.callback_eval:
                    safe_eval(self.callback_eval, {'self': self})
            if tree.get('x_type').lower() == 'void':
                self.write({
                    'state': 'cancel',
                })
            return True
        elif status_code == self._authorize_pending_tx_status:
            self.write({
                'state': 'pending',
                'acquirer_reference': tree.get('x_trans_id'),
            })
            return True
        elif status_code == self._authorize_cancel_tx_status:
            self.write({
                'state': 'cancel',
                'acquirer_reference': tree.get('x_trans_id'),
            })
            return True
        else:
            error = tree.get('x_response_reason_text')
            _logger.info(error)
            self.write({
                'state': 'error',
                'state_message': error,
                'acquirer_reference': tree.get('x_trans_id'),
            })
            return False


class PaymentToken(models.Model):
    _inherit = 'payment.token'

    authorize_profile = fields.Char(string='Alignet Profile ID', help='This contains the unique reference '
                                    'for this partner/payment token combination in the Alignet backend')

    @api.model
    def authorize_create(self, values):
        if values.get('cc_number'):
            values['cc_number'] = values['cc_number'].replace(' ', '')
            acquirer = self.env['payment.acquirer'].browse(values['acquirer_id'])
            expiry = str(values['cc_expiry'][:2]) + str(values['cc_expiry'][-2:])
            partner = self.env['res.partner'].browse(values['partner_id'])
            transaction = AuthorizeAPI(acquirer)
            res = transaction.create_customer_profile(partner, values['cc_number'], expiry, values['cc_cvc'])
            if res.get('profile_id') and res.get('payment_profile_id'):
                return {
                    'authorize_profile': res.get('profile_id'),
                    'name': 'XXXXXXXXXXXX%s - %s' % (values['cc_number'][-4:], values['cc_holder_name']),
                    'acquirer_ref': res.get('payment_profile_id'),
                }
            else:
                raise ValidationError('The Customer Profile creation in Authorize.NET failed.')
        else:
            return values
