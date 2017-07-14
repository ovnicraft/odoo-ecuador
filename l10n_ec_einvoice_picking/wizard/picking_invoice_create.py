# -*- coding: utf-8 -*-


from openerp import fields, models, api


class WizardPicking(models.TransientModel):

    _name = 'picking_invoice_create'
    _description = 'Crear picking y Guia desde Factura'

    carrier_id = fields.Many2one(
        'res.partner', 'Transportista', required=True)
    carrier_plate = fields.Char('Placa', required=True)
    max_date = fields.Date('Fecha máxima de entrega', required=True)
    reason = fields.Many2one('stock.picking.move.reason', 'Motivo de traslado', required=True)
    route = fields.Char('Ruta', required=True)
    authorize_sri = fields.Boolean('Autorizar por el SRI', default=True)
    picking_mode = fields.Selection(
        [('manual', 'Manual'), ('auto', 'Automático')], 'Crear albarán', default='auto', required=True)
    picking_id = fields.Many2one('stock.picking', 'Albarán/Guía')


    @api.one
    def act_create_picking(self):
        invoice = self._context.get('active_id')
        invoice = self.env['account.invoice'].browse(invoice)
        vals = {
            'carrier_id': self.carrier_id.id if 'carrier_id' in self else '',
            'carrier_plate': self.carrier_plate if 'carrier_plate' in self else '',
            'max_date': self.max_date if 'max_date' in self else '',
            'reason_id': self.reason.id if 'reason' in self else '',
            'route': self.route if 'route' in self else '',
            'picking_mode': self.picking_mode if 'picking_mode' in self else '',
            'picking_id': self.picking_id.id if 'picking_id' in self else '',
        }
        # Remove empty items
        vals = {k: v for k, v in vals.items() if v}
        if not self.picking_id:
            invoice.create_picking(vals)
        else:
            self.picking_id.write(vals)

        if self.authorize_sri:
            invoice.action_erefguide_create()
