# -*- coding: utf-8 -*-

from odoo import api, models
from odoo.exceptions import AccessError


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.multi
    def check_deletable(self):
        MODELS_2DELETE = ['account.invoice', 'account.retention']
        if self.res_model not in MODELS_2DELETE:
            return True
        inv = self.env[self.res_model].browse(self.res_id)
        if inv.autorizado_sri:
            return False
        return True

    @api.multi
    def unlink(self):
        for obj in self:
            if not obj.check_deletable():
                raise AccessError('No puede eliminar este adjunto.')
        super(IrAttachment, self).unlink()
        return True
