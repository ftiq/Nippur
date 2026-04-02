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
    filter_client_code = fields.Char()
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
    task_generation_policy = fields.Selection([
        ('create', 'On Plan Creation'),
        ('approve', 'On Approval'),
        ('manual', 'Manual Sync'),
    ], default='approve', required=True)

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
        return self.env['ftiq.plan.candidate.service'].get_client_base_domain()

    def _build_partner_domain(self):
        return self.env['ftiq.plan.candidate.service'].build_filter_domain(self)

    def _build_geo_partner_domain(self, polygon_points=None):
        return self.env['ftiq.plan.candidate.service'].build_geo_domain(polygon_points)

    def _post_filter_partners(self, partners):
        return self.env['ftiq.plan.candidate.service'].post_filter_partners(self, partners)

    def _normalize_geo_polygon(self):
        self.ensure_one()
        return self.env['ftiq.plan.candidate.service'].normalize_geo_polygon(self.geo_polygon)

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
        return self.env['ftiq.plan.candidate.service'].get_filtered_partners(self)

    def _get_geo_partners(self):
        self.ensure_one()
        partners = self.env['ftiq.plan.candidate.service'].get_geo_partners(self)
        self.geo_client_count = len(partners)
        return partners

    def _get_matching_partners(self):
        self.ensure_one()
        return self.env['ftiq.plan.candidate.service'].get_matching_partners(self)

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
        return self.env['ftiq.plan.candidate.service'].get_geo_partner_markers()

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
