# -*- coding: utf-8 -*-
from datetime import date
from odoo import models, fields, api, exceptions
from odoo import tools, _
from odoo.tools.translate import html_translate
from odoo.exceptions import UserError, AccessError


class LocationSession(models.Model):
    _name = 'location.session'
    _description="Get loaction"
    name = fields.Char(string='Session Name', required=True, readonly=True, default=lambda self: _('New'), copy=False)
    state = fields.Selection([
        ('open', 'Open'),
        ('close', 'Close'),
    ],default='open', string='State')
    start_date = fields.Datetime(string='Start Date',default=fields.Datetime.now())
    end_date = fields.Datetime('End Date')
    line_ids = fields.One2many('location.session.line', 'session_id', string='Lines')
    def close_session(self):
        close_date=fields.Datetime.now()
        self.write({'state':'close','end_date':close_date})
        open_line=self.line_ids.filtered(lambda a:a.state=='open')
        for line in open_line:
            line.write({
                'state':'close',
                'end_date':close_date
            })
            
    @api.model
    def create(self, vals):
        open_session=self.env['location.session'].search([('state','=','open'),('create_uid','=',self.env.user.id)],limit=1)
        if open_session:
            raise UserError(_("You cannot open tow sessions at the same time.Please close the old session"))
        if 'latitude' in self._context and 'longitude' in self._context:
            latitude=self._context['latitude']
            longitude=self._context['longitude']
        else:
            raise UserError(_("You cannot open tow without initial location please check internat connection or browser if it support location get"))
        vals['name'] = self.env['ir.sequence'].next_by_code('session.name.seq') or _('New')
        res= super(LocationSession, self).create(vals)
        res.line_ids.create({
            'session_id':res.id,
            'start_date':res.start_date,
            'partner_latitude':latitude,
            'partner_longitude':longitude,
        }) 
        return res
    @api.model
    def store_user_location(self,args):
        open_session=self.env['location.session'].search([('state','=','open'),('create_uid','=',self.env.user.id)],limit=1)
        if open_session:
            open_line=open_session.line_ids.filtered(lambda a:a.state=='open')
            if not open_line or open_line.partner_longitude != str(args['longitude']) or open_line.partner_latitude != str(args['latitude']):
                if open_line:
                    open_line.write({
                        'state':'close',
                        'end_date':fields.Datetime.now()
                    })
                open_session.line_ids.create({
                    'session_id':open_session.id,
                    'start_date':fields.Datetime.now(),
                    'partner_latitude':args['latitude'],
                    'partner_longitude':args['longitude'],
                })
        return True
class LocationSessionLine(models.Model):
    _name = 'location.session.line'
    _description="Get loaction Line"
    state = fields.Selection([
        ('open', 'Open'),
        ('close', 'Close'),
    ],default='open', string='State')
    start_date = fields.Datetime('Start Date')
    end_date = fields.Datetime('End Date')
    partner_latitude = fields.Char('Latitude',default=0)
    partner_longitude = fields.Char('Longitude',default=0)
    session_id = fields.Many2one('location.session', string='Session')
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