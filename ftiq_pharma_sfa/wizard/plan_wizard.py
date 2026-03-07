import json

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FtiqPlanWizard(models.TransientModel):
    _name = 'ftiq.plan.wizard'
    _description = 'Plan Creation Wizard'

    selection_mode = fields.Selection([
        ('filter', 'Clients Select'),
        ('geo', 'Clients GEO'),
    ], default='filter', required=True)
    step = fields.Selection([
        ('type', 'Type'),
        ('configure', 'Configure'),
        ('clients', 'Clients'),
        ('setup', 'Set'),
    ], default='type')

    plan_name = fields.Char()
    task_type_id = fields.Many2one('ftiq.task.type')
    team_id = fields.Many2one('crm.team', string='Sales Team')
    user_id = fields.Many2one('res.users')
    allowed_team_ids = fields.Many2many('crm.team', compute='_compute_allowed_team_ids')
    allowed_user_ids = fields.Many2many('res.users', compute='_compute_allowed_user_ids')
    schedule_date = fields.Date()
    note = fields.Text()
    apply_to_all = fields.Boolean(default=False)

    filter_name = fields.Char()
    filter_partner_id = fields.Many2one('res.partner')
    filter_country_id = fields.Many2one('res.country', default=lambda self: self.env.company.country_id)
    filter_city_id = fields.Many2one('ftiq.city')
    filter_area_id = fields.Many2one('ftiq.area')
    filter_address = fields.Char()
    filter_client_category_id = fields.Many2one('ftiq.client.category')
    filter_specialty_id = fields.Many2one('ftiq.specialty')
    filter_subspecialty_id = fields.Many2one('ftiq.subspecialty')
    filter_classification_id = fields.Many2one('ftiq.client.classification')
    filter_has_cashed = fields.Selection([
        ('all', 'All'), ('yes', 'Yes'), ('no', 'No'),
    ], default='all')
    filter_has_tasks = fields.Selection([
        ('all', 'All'), ('yes', 'Yes'), ('no', 'No'),
    ], default='all')
    filter_geo_confirmed = fields.Boolean()
    filter_app_verified = fields.Boolean()
    filter_license_attached = fields.Boolean()

    geo_polygon = fields.Text()
    geo_client_count = fields.Integer(readonly=True)
    geo_map_field = fields.Char()

    candidate_partner_ids = fields.Many2many(
        'res.partner',
        'ftiq_plan_wizard_candidate_partner_rel',
        'wizard_id',
        'partner_id',
    )
    candidate_partner_count = fields.Integer(readonly=True)
    client_review_name = fields.Char(default='')
    partner_ids = fields.Many2many('res.partner', 'ftiq_plan_wizard_partner_rel', 'wizard_id', 'partner_id')

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        team = self.env['ftiq.weekly.plan']._get_plannable_teams()[:1]
        if team and 'team_id' in fields_list:
            values.setdefault('team_id', team.id)
        if team and 'user_id' in fields_list:
            default_user = self.env['ftiq.weekly.plan']._get_team_representatives(team)[:1]
            if default_user:
                values.setdefault('user_id', default_user.id)
        return values

    def _compute_allowed_team_ids(self):
        allowed_teams = self.env['ftiq.weekly.plan']._get_plannable_teams()
        for wizard in self:
            wizard.allowed_team_ids = allowed_teams

    @api.depends('team_id')
    def _compute_allowed_user_ids(self):
        plan_model = self.env['ftiq.weekly.plan']
        for wizard in self:
            wizard.allowed_user_ids = plan_model._get_team_representatives(wizard.team_id)

    def action_choose_filter(self):
        self.ensure_one()
        self.selection_mode = 'filter'
        return self._reopen()

    def action_choose_geo(self):
        self.ensure_one()
        self.selection_mode = 'geo'
        return self._reopen()

    @api.onchange('team_id')
    def _onchange_team_id(self):
        for wizard in self:
            allowed_users = self.env['ftiq.weekly.plan']._get_team_representatives(wizard.team_id)
            if wizard.user_id and wizard.user_id not in allowed_users:
                wizard.user_id = False

    @api.onchange('filter_partner_id')
    def _onchange_filter_partner_id(self):
        for wizard in self:
            partner = wizard.filter_partner_id
            if not partner:
                continue
            wizard.filter_country_id = partner.country_id or wizard.filter_country_id
            wizard.filter_city_id = partner.ftiq_city_id
            wizard.filter_area_id = partner.ftiq_area_id
            wizard.filter_address = partner.street
            wizard.filter_client_category_id = partner.ftiq_client_category_id
            wizard.filter_specialty_id = partner.ftiq_specialty_id
            wizard.filter_subspecialty_id = partner.ftiq_subspecialty_id
            wizard.filter_classification_id = partner.ftiq_classification_id

    @api.onchange('filter_country_id')
    def _onchange_filter_country_id(self):
        for wizard in self:
            if wizard.filter_city_id and wizard.filter_city_id.country_id != wizard.filter_country_id:
                wizard.filter_city_id = False
            if wizard.filter_area_id and wizard.filter_area_id.city_id != wizard.filter_city_id:
                wizard.filter_area_id = False

    @api.onchange('filter_city_id')
    def _onchange_filter_city_id(self):
        for wizard in self:
            if wizard.filter_city_id and wizard.filter_city_id.country_id and wizard.filter_country_id != wizard.filter_city_id.country_id:
                wizard.filter_country_id = wizard.filter_city_id.country_id
            if wizard.filter_area_id and wizard.filter_area_id.city_id != wizard.filter_city_id:
                wizard.filter_area_id = False

    @api.onchange('filter_specialty_id')
    def _onchange_filter_specialty_id(self):
        for wizard in self:
            if wizard.filter_subspecialty_id and wizard.filter_subspecialty_id.specialty_id != wizard.filter_specialty_id:
                wizard.filter_subspecialty_id = False

    def _get_client_base_domain(self):
        return [
            '|', '|', '|',
            ('is_ftiq_doctor', '=', True),
            ('is_ftiq_center', '=', True),
            ('is_ftiq_pharmacy', '=', True),
            ('ftiq_client_category_id', '!=', False),
        ]

    def _build_partner_domain(self):
        domain = list(self._get_client_base_domain())
        if self.filter_partner_id:
            domain.append(('id', '=', self.filter_partner_id.id))
        if self.filter_name:
            domain.append(('name', 'ilike', self.filter_name))
        if self.filter_country_id:
            domain.append(('country_id', '=', self.filter_country_id.id))
        if self.filter_city_id:
            domain.append(('ftiq_city_id', '=', self.filter_city_id.id))
        if self.filter_area_id:
            domain.append(('ftiq_area_id', '=', self.filter_area_id.id))
        if self.filter_address:
            domain.append(('street', 'ilike', self.filter_address))
        if self.filter_client_category_id:
            domain.append(('ftiq_client_category_id', '=', self.filter_client_category_id.id))
        if self.filter_specialty_id:
            domain.append(('ftiq_specialty_id', '=', self.filter_specialty_id.id))
        if self.filter_subspecialty_id:
            domain.append(('ftiq_subspecialty_id', '=', self.filter_subspecialty_id.id))
        if self.filter_classification_id:
            domain.append(('ftiq_classification_id', '=', self.filter_classification_id.id))
        if self.filter_geo_confirmed:
            domain.append(('ftiq_geo_confirmed', '=', True))
        if self.filter_app_verified:
            domain.append(('ftiq_app_verified', '=', True))
        if self.filter_license_attached:
            domain.append(('ftiq_license_attached', '=', True))
        return domain

    def _build_geo_partner_domain(self, polygon_points=None):
        domain = list(self._get_client_base_domain())
        domain.extend([
            ('partner_latitude', '!=', False),
            ('partner_longitude', '!=', False),
        ])
        if polygon_points:
            longitudes = [point[0] for point in polygon_points]
            latitudes = [point[1] for point in polygon_points]
            domain.extend([
                ('partner_longitude', '>=', min(longitudes)),
                ('partner_longitude', '<=', max(longitudes)),
                ('partner_latitude', '>=', min(latitudes)),
                ('partner_latitude', '<=', max(latitudes)),
            ])
        return domain

    def _post_filter_partners(self, partners):
        if self.filter_has_cashed == 'yes':
            has_payment = self.env['account.payment'].sudo().search([
                ('is_field_collection', '=', True),
                ('partner_id', 'in', partners.ids),
                ('state', 'in', ('in_process', 'paid')),
            ]).mapped('partner_id')
            partners = partners & has_payment
        elif self.filter_has_cashed == 'no':
            has_payment = self.env['account.payment'].sudo().search([
                ('is_field_collection', '=', True),
                ('partner_id', 'in', partners.ids),
                ('state', 'in', ('in_process', 'paid')),
            ]).mapped('partner_id')
            partners = partners - has_payment
        if self.filter_has_tasks == 'yes':
            has_task = self.env['ftiq.daily.task'].sudo().search([
                ('partner_id', 'in', partners.ids),
                ('state', '!=', 'cancelled'),
            ]).mapped('partner_id')
            partners = partners & has_task
        elif self.filter_has_tasks == 'no':
            has_task = self.env['ftiq.daily.task'].sudo().search([
                ('partner_id', 'in', partners.ids),
                ('state', '!=', 'cancelled'),
            ]).mapped('partner_id')
            partners = partners - has_task
        return partners

    def _normalize_geo_polygon(self):
        self.ensure_one()
        if not self.geo_polygon:
            return []
        try:
            raw_polygon = json.loads(self.geo_polygon)
        except (TypeError, ValueError):
            return []
        points = []
        if isinstance(raw_polygon, dict):
            coordinates = raw_polygon.get('coordinates') or []
            if raw_polygon.get('type') == 'Polygon' and coordinates:
                points = coordinates[0]
        elif isinstance(raw_polygon, list):
            points = raw_polygon
        normalized_points = []
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            try:
                longitude = float(point[0])
                latitude = float(point[1])
            except (TypeError, ValueError):
                continue
            normalized_points.append((longitude, latitude))
        if len(normalized_points) > 1 and normalized_points[0] == normalized_points[-1]:
            normalized_points = normalized_points[:-1]
        return normalized_points if len(normalized_points) >= 3 else []

    @staticmethod
    def _point_in_polygon(longitude, latitude, polygon_points):
        inside = False
        previous_index = len(polygon_points) - 1
        for index, (current_longitude, current_latitude) in enumerate(polygon_points):
            previous_longitude, previous_latitude = polygon_points[previous_index]
            latitude_crossed = (current_latitude > latitude) != (previous_latitude > latitude)
            if latitude_crossed:
                edge_latitude_delta = previous_latitude - current_latitude or 1e-12
                edge_longitude = (
                    (previous_longitude - current_longitude) * (latitude - current_latitude) / edge_latitude_delta
                ) + current_longitude
                if longitude < edge_longitude:
                    inside = not inside
            previous_index = index
        return inside

    def _get_filtered_partners(self):
        self.ensure_one()
        partners = self.env['res.partner'].search(self._build_partner_domain(), order='name')
        return self._post_filter_partners(partners)

    def _get_geo_partners(self):
        self.ensure_one()
        polygon_points = self._normalize_geo_polygon()
        if not polygon_points:
            raise ValidationError(_('Draw an area on the map before continuing.'))
        candidate_partners = self.env['res.partner'].search(
            self._build_geo_partner_domain(polygon_points),
            order='name',
        )
        partners_in_polygon = candidate_partners.filtered(
            lambda partner: self._point_in_polygon(
                partner.partner_longitude,
                partner.partner_latitude,
                polygon_points,
            )
        )
        if not partners_in_polygon:
            raise ValidationError(_('No clients were found inside the selected area.'))
        self.geo_client_count = len(partners_in_polygon)
        return partners_in_polygon

    def _get_matching_partners(self):
        self.ensure_one()
        if self.selection_mode == 'geo':
            return self._get_geo_partners()
        return self._get_filtered_partners()

    def _set_candidate_partners(self, partners):
        self.ensure_one()
        self.candidate_partner_ids = [(6, 0, partners.ids)]
        self.partner_ids = [(6, 0, partners.ids)]
        self.candidate_partner_count = len(partners)
        self.client_review_name = ''
        if self.selection_mode != 'geo':
            self.geo_client_count = 0

    def _get_partner_client_type(self, partner):
        partner.ensure_one()
        if partner.is_ftiq_doctor:
            return 'doctor'
        if partner.is_ftiq_center:
            return 'center'
        if partner.is_ftiq_pharmacy:
            return 'pharmacy'
        return 'client'

    @api.model
    def get_geo_partner_markers(self):
        partners = self.env['res.partner'].search(self._build_geo_partner_domain(), order='name')
        markers = []
        for partner in partners:
            address_parts = [
                partner.street,
                partner.ftiq_area_id.name,
                partner.ftiq_city_id.name,
                partner.country_id.name,
            ]
            markers.append({
                'id': partner.id,
                'name': partner.name,
                'latitude': partner.partner_latitude,
                'longitude': partner.partner_longitude,
                'client_type': self._get_partner_client_type(partner),
                'category': partner.ftiq_client_category_id.name or '',
                'specialty': partner.ftiq_specialty_id.name or '',
                'classification': partner.ftiq_classification_id.name or '',
                'address': ', '.join(part for part in address_parts if part),
                'area': partner.ftiq_area_id.name or '',
                'city': partner.ftiq_city_id.name or partner.city or '',
                'geo_confirmed': bool(partner.ftiq_geo_confirmed),
            })
        return markers

    def action_next(self):
        self.ensure_one()
        if self.step == 'type':
            self.step = 'configure'
        elif self.step == 'configure':
            partners = self._get_matching_partners()
            self._set_candidate_partners(partners)
            self.step = 'clients'
        elif self.step == 'clients':
            self.step = 'setup'
        elif self.step == 'setup':
            return self._create_plan()
        return self._reopen()

    def action_back(self):
        self.ensure_one()
        if self.step == 'configure':
            self.step = 'type'
        elif self.step == 'clients':
            self.step = 'configure'
        elif self.step == 'setup':
            self.step = 'clients'
        return self._reopen()

    def action_select_all(self):
        self.ensure_one()
        self.partner_ids = [(6, 0, self.candidate_partner_ids.ids)]
        return self._reopen()

    def action_deselect_all(self):
        self.ensure_one()
        self.partner_ids = [(5, 0, 0)]
        return self._reopen()

    def _create_plan(self):
        if not self.team_id:
            raise ValidationError(_('Select a sales team before creating the plan.'))
        if not self.partner_ids:
            raise ValidationError(_('Select at least one client before creating the plan.'))
        plan_model = self.env['ftiq.weekly.plan']
        schedule_date = self.schedule_date or fields.Date.today()
        plan_name = plan_model._build_plan_display_name(self.team_id, schedule_date, self.plan_name)
        plan = plan_model.with_context(skip_assignment_notification=True).create({
            'name': plan_name,
            'team_id': self.team_id.id,
            'task_type_id': self.task_type_id.id if self.task_type_id else False,
            'week_start': schedule_date,
            'note': self.note,
        })
        line_values = []
        for partner in self.partner_ids:
            line_values.append({
                'plan_id': plan.id,
                'user_id': self.user_id.id if self.user_id else False,
                'partner_id': partner.id,
                'scheduled_date': schedule_date,
            })
        self.env['ftiq.weekly.plan.line'].create(line_values)
        plan._notify_assignment()
        plan._sync_project_and_tasks(create_project=True, create_daily_tasks=True)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ftiq.weekly.plan',
            'res_id': plan.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
