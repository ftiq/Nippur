# -*- coding: utf-8 -*-
from datetime import date
from odoo import models, fields, api, exceptions
from odoo import tools, _
from odoo.tools.translate import html_translate
from odoo.exceptions import UserError, AccessError


class ResPartner(models.Model):
    _inherit = 'res.partner'
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