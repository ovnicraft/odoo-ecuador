# -*- coding: utf-8 -*-
# © <2016> <Cristian Salamea>
# © <2017> <Jonathan Finlay>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import api, models, fields, _

from openerp.tools.float_utils import float_compare
from openerp.exceptions import Warning as UserError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    auth_erefguide_id = fields.Many2one(
        'account.authorisation',
        'Para Guías'
    )
    do_invoice_picking = fields.Boolean(
        'Crear Albarán/Guía',
        help="Crear Albarán/Guía automáticamente?")


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.one
    @api.depends('picking_id.autorizado_sri')
    def picking_autorizado(self):
        return self.picking_id.autorizado_sri

    picking_id = fields.Many2one('stock.picking', 'Albarán/Guía')
    picking_autorizado = fields.Boolean('Guía autorizada', related='picking_id.autorizado_sri')

    @api.multi
    def action_erefguide_wizard(self):
        self.ensure_one()
        context = {}
        if self.picking_id:
            context['default_picking_id'] = self.picking_id.id
            context['default_picking_mode'] = 'manual'
            context['default_carrier_id'] = self.picking_id.carrier_id.id if self.picking_id.carrier_id else ''
            context['default_carrier_plate'] = self.picking_id.carrier_plate if self.picking_id.carrier_plate else ''
            context['default_reason'] = self.picking_id.reason_id.id if self.picking_id.reason_id else ''
            context['default_route'] = self.picking_id.route if self.picking_id.route else ''
            context['default_max_date'] = self.picking_id.max_date if self.picking_id.max_date else ''

        action = self.env.ref('l10n_ec_einvoice_picking.action_erefguide_wizard').read()[0]
        action['context'] = context
        return action

    @api.multi
    def action_generate_erefguide(self):
        for obj in self:
            if not obj.journal_id.auth_erefguide_id.is_electronic:
                return True
            obj.picking_id.action_generate_document()

    @api.multi
    def action_erefguide_create(self):
        for obj in self:
            if obj.type != 'out_invoice':
                raise UserError('No puede generar guías para este tipo de documento')
            if not obj.autorizado_sri:
                raise UserError('La factura debe estar autorizada por el SRI')
            obj.action_generate_erefguide()

    @api.model
    def _prepare_picking(self, vals=None):
        # TODO: picking_type_id, location_id
        picking_type = self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)  # noqa
        if not self.partner_id.property_stock_customer.id:
            raise UserError(_("You must set a Customer Location for this partner %s") % self.partner_id.name)  # noqa
        res = {
            'picking_type_id': picking_type.id,
            'partner_id': self.partner_id.id,
            'date': self.date_invoice,
            'origin': self.reference,
            'location_dest_id': self.partner_id.property_stock_customer.id,
            'location_id': picking_type.default_location_src_id.id,
            'company_id': self.company_id.id,
            'auth_id': self.journal_id.auth_erefguide_id.id,
        }
        if vals:
            for key, item in vals.items():
                res[key] = item
        return res

    @api.one
    def create_picking(self, vals=None):
        StockPicking = self.env['stock.picking']
        if any([ptype in ['product', 'consu'] for ptype in self.invoice_line_ids.mapped('product_id.type')]):  # noqa
            res = self._prepare_picking(vals)
            picking = StockPicking.create(res)
            moves = self.invoice_line_ids._create_stock_moves(picking)
            moves = moves.filtered(lambda x: x.state not in ('done', 'cancel')).action_confirm()  # noqa
            moves.force_assign()
            picking.do_transfer()
            self.picking_id = picking
        return True


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    @api.multi
    def _get_stock_move_price_unit(self):
        self.ensure_one()
        line = self[0]
        invoice = line.invoice_id
        price_unit = line.price_unit
        if line.invoice_line_tax_ids:
            price_unit = \
            line.invoice_line_tax_ids.with_context(round=False).compute_all(price_unit, currency=invoice.currency_id,
                                                                            quantity=1.0)['total_excluded']  # noqa
        if line.uom_id.id != line.product_id.uom_id.id:
            price_unit *= line.uom_id.factor / line.product_id.uom_id.factor  # noqa
        if invoice.currency_id != invoice.company_id.currency_id:
            price_unit = invoice.currency_id.compute(price_unit, invoice.company_id.currency_id, round=False)  # noqa
        return price_unit

    @api.multi
    def _create_stock_moves(self, picking):
        moves = self.env['stock.move']
        done = self.env['stock.move'].browse()
        for line in self:
            if line.product_id.type not in ['product', 'consu']:
                continue
            qty = 0.0
            price_unit = line._get_stock_move_price_unit()
            template = {
                'name': line.name or '',
                'product_id': line.product_id.id,
                'product_uom': line.uom_id.id,
                'date': line.invoice_id.date_invoice,
                'date_expected': line.invoice_id.date_invoice,
                'location_id': picking.picking_type_id.default_location_src_id.id,  # noqa
                'location_dest_id': line.invoice_id.partner_id.property_stock_customer.id,  # noqa
                'picking_id': picking.id,
                'partner_id': line.invoice_id.partner_id.id,
                'move_dest_id': False,
                'state': 'draft',
                'company_id': line.invoice_id.company_id.id,
                'price_unit': price_unit,
                'picking_type_id': picking.picking_type_id.id,
                'procurement_id': False,
                'origin': line.invoice_id.invoice_number,
                'route_ids': picking.picking_type_id.warehouse_id and [
                    (6, 0, [x.id for x in picking.picking_type_id.warehouse_id.route_ids])] or [],  # noqa
                'warehouse_id': picking.picking_type_id.warehouse_id.id,
            }
            # Fullfill all related procurements with this po line
            diff_quantity = line.quantity - qty
            if float_compare(diff_quantity, 0.0, precision_rounding=line.uom_id.rounding) > 0:  # noqa
                template['product_uom_qty'] = diff_quantity
                done += moves.create(template)
        return done

