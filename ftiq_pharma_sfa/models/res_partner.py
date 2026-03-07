from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_ftiq_doctor = fields.Boolean(default=False)
    is_ftiq_center = fields.Boolean(default=False)
    is_ftiq_pharmacy = fields.Boolean(default=False)

    ftiq_specialty_id = fields.Many2one('ftiq.specialty')
    ftiq_subspecialty_id = fields.Many2one('ftiq.subspecialty')
    ftiq_classification_id = fields.Many2one('ftiq.client.classification')
    ftiq_prescriber_status_id = fields.Many2one('ftiq.prescriber.status')
    ftiq_official_type_id = fields.Many2one('ftiq.official.type')
    ftiq_speaker_level_id = fields.Many2one('ftiq.speaker.level')
    ftiq_leadership_level_id = fields.Many2one('ftiq.leadership.level')
    ftiq_workplace_type_id = fields.Many2one('ftiq.workplace.type')
    ftiq_debt_classification_id = fields.Many2one('ftiq.debt.classification')
    ftiq_color_code_id = fields.Many2one('ftiq.color.code')
    ftiq_general_note = fields.Text()

    ftiq_nickname = fields.Char()
    ftiq_birthday = fields.Date()
    ftiq_spouse_name = fields.Char()
    ftiq_spouse_birthday = fields.Date()
    ftiq_kid1_name = fields.Char()
    ftiq_kid1_birthday = fields.Date()
    ftiq_kid2_name = fields.Char()
    ftiq_kid2_birthday = fields.Date()
    ftiq_kid3_name = fields.Char()
    ftiq_kid3_birthday = fields.Date()

    ftiq_area_id = fields.Many2one('ftiq.area')
    ftiq_city_id = fields.Many2one('ftiq.city')
    ftiq_geo_confirmed = fields.Boolean(default=False)
    ftiq_app_verified = fields.Boolean(default=False)
    ftiq_license_attached = fields.Boolean(default=False)

    ftiq_answer_ids = fields.One2many('ftiq.client.answer', 'partner_id')
    ftiq_visit_ids = fields.One2many('ftiq.visit', 'partner_id')
    ftiq_last_visit_date = fields.Date(compute='_compute_ftiq_visit_stats', store=True)
    ftiq_total_visits = fields.Integer(compute='_compute_ftiq_visit_stats', store=True)
    ftiq_order_count = fields.Integer(compute='_compute_ftiq_order_count', string='Orders')
    ftiq_collection_count = fields.Integer(compute='_compute_ftiq_collection_count', string='Collections')
    ftiq_invoice_count = fields.Integer(compute='_compute_ftiq_invoice_count', string='Invoices')

    @api.depends('ftiq_visit_ids', 'ftiq_visit_ids.visit_date', 'ftiq_visit_ids.state')
    def _compute_ftiq_visit_stats(self):
        for rec in self:
            visits = rec.ftiq_visit_ids.filtered(lambda v: v.state in ('submitted', 'approved'))
            rec.ftiq_total_visits = len(visits)
            if visits:
                rec.ftiq_last_visit_date = max(visits.mapped('visit_date'))
            else:
                rec.ftiq_last_visit_date = False

    def _compute_ftiq_order_count(self):
        sale_order_obj = self.env['sale.order'].sudo()
        for rec in self:
            rec.ftiq_order_count = sale_order_obj.search_count([
                ('partner_id', '=', rec.id),
                ('is_field_order', '=', True),
            ])

    def _compute_ftiq_collection_count(self):
        payment_obj = self.env['account.payment'].sudo()
        for rec in self:
            rec.ftiq_collection_count = payment_obj.search_count([
                ('partner_id', '=', rec.id),
                ('is_field_collection', '=', True),
            ])

    def _compute_ftiq_invoice_count(self):
        invoice_obj = self.env['account.move'].sudo()
        for rec in self:
            rec.ftiq_invoice_count = invoice_obj.search_count([
                ('partner_id', '=', rec.id),
                ('move_type', '=', 'out_invoice'),
            ])

    def action_open_ftiq_visits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Visits'),
            'res_model': 'ftiq.visit',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def action_open_ftiq_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Field Orders'),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id), ('is_field_order', '=', True)],
            'context': {'default_partner_id': self.id, 'default_is_field_order': True},
        }

    def action_open_ftiq_collections(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cash Collections'),
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id), ('is_field_collection', '=', True)],
            'context': {'default_partner_id': self.id, 'default_is_field_collection': True},
        }

    def action_open_ftiq_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id), ('move_type', '=', 'out_invoice')],
        }

    def action_open_whatsapp(self):
        self.ensure_one()
        phone = self.mobile or self.phone or ''
        phone = phone.replace(' ', '').replace('+', '').replace('-', '')
        return {
            'type': 'ir.actions.act_url',
            'url': 'https://wa.me/%s' % phone,
            'target': 'new',
        }
