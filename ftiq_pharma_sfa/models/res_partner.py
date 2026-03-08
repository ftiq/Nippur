from odoo import models, fields, api, _


FTIQ_CLIENT_TYPES = [
    ('doctor', 'Doctor'),
    ('center', 'Center'),
    ('pharmacy', 'Pharmacy'),
    ('client', 'Client'),
]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_ftiq_doctor = fields.Boolean(default=False)
    is_ftiq_center = fields.Boolean(default=False)
    is_ftiq_pharmacy = fields.Boolean(default=False)
    ftiq_client_category_id = fields.Many2one('ftiq.client.category', string='Client Category')
    ftiq_client_code = fields.Char(copy=False, index=True)
    ftiq_client_type = fields.Selection(FTIQ_CLIENT_TYPES, compute='_compute_ftiq_client_profile', store=True)
    ftiq_client_type_label = fields.Char(compute='_compute_ftiq_client_profile')
    ftiq_is_field_client = fields.Boolean(compute='_compute_ftiq_client_profile', store=True)

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
    ftiq_execution_address = fields.Char(compute='_compute_ftiq_execution_readiness')
    ftiq_geo_ready = fields.Boolean(compute='_compute_ftiq_execution_readiness', store=True)

    ftiq_answer_ids = fields.One2many('ftiq.client.answer', 'partner_id')
    ftiq_visit_ids = fields.One2many('ftiq.visit', 'partner_id')
    ftiq_last_visit_date = fields.Date(compute='_compute_ftiq_visit_stats', store=True)
    ftiq_total_visits = fields.Integer(compute='_compute_ftiq_visit_stats', store=True)
    ftiq_order_count = fields.Integer(compute='_compute_ftiq_order_count', string='Orders')
    ftiq_collection_count = fields.Integer(compute='_compute_ftiq_collection_count', string='Collections')
    ftiq_invoice_count = fields.Integer(compute='_compute_ftiq_invoice_count', string='Invoices')
    ftiq_open_invoice_amount = fields.Float(
        string='Open Invoice Residual',
        digits='Product Price',
        compute='_compute_ftiq_invoice_count',
    )

    @api.depends('is_ftiq_doctor', 'is_ftiq_center', 'is_ftiq_pharmacy', 'ftiq_client_category_id')
    def _compute_ftiq_client_profile(self):
        selection_map = dict(self._fields['ftiq_client_type'].selection)
        for rec in self:
            if rec.is_ftiq_doctor:
                client_type = 'doctor'
            elif rec.is_ftiq_center:
                client_type = 'center'
            elif rec.is_ftiq_pharmacy:
                client_type = 'pharmacy'
            elif rec.ftiq_client_category_id:
                client_type = 'client'
            else:
                client_type = False
            rec.ftiq_client_type = client_type
            rec.ftiq_is_field_client = bool(client_type)
            rec.ftiq_client_type_label = selection_map.get(client_type, _('Client')) if client_type else ''

    @api.depends(
        'street',
        'city',
        'country_id',
        'ftiq_city_id',
        'ftiq_area_id',
        'ftiq_geo_confirmed',
        'partner_latitude',
        'partner_longitude',
    )
    def _compute_ftiq_execution_readiness(self):
        for rec in self:
            address_parts = [
                rec.street,
                rec.ftiq_area_id.name,
                rec.ftiq_city_id.name or rec.city,
                rec.country_id.name,
            ]
            rec.ftiq_execution_address = ', '.join(part for part in address_parts if part)
            rec.ftiq_geo_ready = bool(rec.ftiq_geo_confirmed and rec.partner_latitude and rec.partner_longitude)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_ftiq_client_code()
        return records

    def write(self, vals):
        result = super().write(vals)
        if any(
            key in vals
            for key in ('is_ftiq_doctor', 'is_ftiq_center', 'is_ftiq_pharmacy', 'ftiq_client_category_id')
        ):
            self._ensure_ftiq_client_code()
        return result

    def _get_ftiq_client_type_key(self):
        self.ensure_one()
        if self.is_ftiq_doctor:
            return 'doctor'
        if self.is_ftiq_center:
            return 'center'
        if self.is_ftiq_pharmacy:
            return 'pharmacy'
        if self.ftiq_client_category_id:
            return 'client'
        return False

    def _generate_ftiq_client_code(self):
        self.ensure_one()
        prefix_map = {
            'doctor': 'DOC',
            'center': 'CTR',
            'pharmacy': 'PHA',
            'client': 'CLI',
        }
        return '%s-%05d' % (prefix_map.get(self._get_ftiq_client_type_key() or 'client', 'CLI'), self.id)

    def _ensure_ftiq_client_code(self):
        for rec in self.filtered(lambda partner: partner._get_ftiq_client_type_key() and not partner.ftiq_client_code):
            rec.ftiq_client_code = rec._generate_ftiq_client_code()

    @api.onchange('country_id')
    def _onchange_ftiq_country_id(self):
        for rec in self:
            if rec.ftiq_city_id and rec.ftiq_city_id.country_id and rec.ftiq_city_id.country_id != rec.country_id:
                rec.ftiq_city_id = False
                rec.ftiq_area_id = False

    @api.onchange('ftiq_city_id')
    def _onchange_ftiq_city_id(self):
        for rec in self:
            if rec.ftiq_city_id and rec.ftiq_city_id.country_id and rec.country_id != rec.ftiq_city_id.country_id:
                rec.country_id = rec.ftiq_city_id.country_id
            if rec.ftiq_area_id and rec.ftiq_area_id.city_id != rec.ftiq_city_id:
                rec.ftiq_area_id = False

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
                ('state', 'in', ('in_process', 'paid')),
            ])

    def _compute_ftiq_invoice_count(self):
        invoice_obj = self.env['account.move'].sudo()
        for rec in self:
            invoices = invoice_obj.search([
                ('partner_id', 'child_of', rec.commercial_partner_id.id),
                ('move_type', '=', 'out_invoice'),
            ])
            rec.ftiq_invoice_count = len(invoices)
            rec.ftiq_open_invoice_amount = sum(
                invoices.filtered(lambda invoice: invoice.state == 'posted' and invoice.amount_residual > 0).mapped('amount_residual')
            )

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
            'context': {
                'default_partner_id': self.id,
                'default_is_field_collection': True,
                'default_ftiq_user_id': self.env.uid,
            },
        }

    def action_open_ftiq_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('partner_id', 'child_of', self.commercial_partner_id.id), ('move_type', '=', 'out_invoice')],
            'context': {'default_move_type': 'out_invoice'},
        }

    def action_open_ftiq_client_search(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'name': _('Client Search'),
            'tag': 'ftiq_pharma_sfa.client_search',
            'context': {'default_partner_id': self.id},
        }

    @api.model
    def ftiq_search_clients(
        self,
        search_term='',
        client_code='',
        country_id=False,
        city_id=False,
        area_id=False,
        latitude=False,
        longitude=False,
        radius_km=0.0,
        limit=25,
    ):
        return self.env['ftiq.client.search.service'].search_clients(
            search_term=search_term,
            client_code=client_code,
            country_id=country_id,
            city_id=city_id,
            area_id=area_id,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            limit=limit,
        )

    @api.model
    def ftiq_get_client_card(self, partner_id, latitude=False, longitude=False):
        return self.env['ftiq.client.search.service'].get_client_card(
            partner_id,
            latitude=latitude,
            longitude=longitude,
        )

    def action_open_whatsapp(self):
        self.ensure_one()
        phone = self.mobile or self.phone or ''
        phone = phone.replace(' ', '').replace('+', '').replace('-', '')
        return {
            'type': 'ir.actions.act_url',
            'url': 'https://wa.me/%s' % phone,
            'target': 'new',
        }
