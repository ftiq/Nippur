from odoo import models, fields, api, _


class FtiqPlanWizard(models.TransientModel):
    _name = 'ftiq.plan.wizard'
    _description = 'Plan Creation Wizard'

    step = fields.Selection([
        ('type', 'Type'),
        ('configure', 'Configure'),
        ('clients', 'Clients'),
    ], default='type')

    plan_name = fields.Char()
    task_type_id = fields.Many2one('ftiq.task.type')
    user_id = fields.Many2one('res.users')
    schedule_date = fields.Date()
    note = fields.Text()
    apply_to_all = fields.Boolean(default=False)

    filter_name = fields.Char()
    filter_country_id = fields.Many2one('res.country')
    filter_city_id = fields.Many2one('ftiq.city')
    filter_area_id = fields.Many2one('ftiq.area')
    filter_address = fields.Char()
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

    partner_ids = fields.Many2many('res.partner', 'ftiq_plan_wizard_partner_rel', 'wizard_id', 'partner_id')

    def _build_partner_domain(self):
        domain = ['|', ('is_ftiq_doctor', '=', True), ('is_ftiq_center', '=', True)]
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

    def action_next(self):
        self.ensure_one()
        if self.step == 'type':
            self.step = 'configure'
        elif self.step == 'configure':
            domain = self._build_partner_domain()
            partners = self.env['res.partner'].search(domain)
            self.partner_ids = [(6, 0, partners.ids)]
            self.step = 'clients'
        elif self.step == 'clients':
            return self._create_plan()
        return self._reopen()

    def action_back(self):
        self.ensure_one()
        if self.step == 'configure':
            self.step = 'type'
        elif self.step == 'clients':
            self.step = 'configure'
        return self._reopen()

    def action_select_all(self):
        self.ensure_one()
        domain = self._build_partner_domain()
        partners = self.env['res.partner'].search(domain)
        self.partner_ids = [(6, 0, partners.ids)]
        return self._reopen()

    def action_deselect_all(self):
        self.ensure_one()
        self.partner_ids = [(5, 0, 0)]
        return self._reopen()

    def _create_plan(self):
        plan = self.env['ftiq.weekly.plan'].create({
            'name': self.plan_name or _('New Plan'),
            'user_id': self.user_id.id if self.user_id else self.env.uid,
            'task_type_id': self.task_type_id.id if self.task_type_id else False,
            'week_start': self.schedule_date or fields.Date.today(),
            'note': self.note,
        })
        for partner in self.partner_ids:
            self.env['ftiq.weekly.plan.line'].create({
                'plan_id': plan.id,
                'partner_id': partner.id,
                'scheduled_date': self.schedule_date or fields.Date.today(),
            })
        # Generate linked project/tasks immediately so planning is mirrored to standard Project app.
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
