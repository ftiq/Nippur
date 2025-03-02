# -*- coding: utf-8 -*-
from datetime import date
from odoo import models, fields, api, exceptions
from odoo import tools, _
from odoo.tools.translate import html_translate
from odoo.exceptions import UserError, AccessError


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    partner_latitude = fields.Char('Latitude')
    partner_longitude = fields.Char('Longitude')
    
    @api.model
    def create(self, vals):
        has_location=False
        if 'partner_latitude' in self._context and 'partner_longitude' in self._context:
            has_location=True
            vals['partner_latitude']=self._context['partner_latitude']
            vals['partner_longitude']=self._context['partner_longitude']
        res =super(SaleOrder, self).create(vals)
        if has_location and (res.partner_id.partner_latitude ==0 or res.partner_id.partner_longitude==0):
            res.partner_id.partner_latitude=vals['partner_latitude']
            res.partner_id.partner_longitude=vals['partner_longitude']
        return res
    def show_map(self):
        if self.partner_latitude and self.partner_longitude:
            url = f"https://www.google.com/maps?q={self.partner_latitude},{self.partner_longitude}"
            return {
                'type': 'ir.actions.act_url',
                'url': url,
                'target': 'new',  # Open in a new tab
            }
        else:
            raise UserError(_("Please provide both latitude and longitude for this partner."))