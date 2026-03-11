from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class FtiqWeeklyPlan(models.Model):
    _name = 'ftiq.weekly.plan'
    _description = 'Weekly Visit Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'week_start desc'

    name = fields.Char(required=True, tracking=True)
    team_id = fields.Many2one(
        'crm.team',
        string='Sales Team',
        tracking=True,
        default=lambda self: self._default_team_id(),
    )
    user_id = fields.Many2one(
        'res.users',
        string='Primary Representative',
        compute='_compute_user_id',
        store=True,
        readonly=True,
    )
    supervisor_id = fields.Many2one(
        'res.users',
        string='Team Manager',
        related='team_id.user_id',
        store=True,
        readonly=True,
    )
    allowed_team_ids = fields.Many2many('crm.team', compute='_compute_allowed_team_ids')
    allowed_user_ids = fields.Many2many('res.users', compute='_compute_allowed_user_ids')
    task_type_id = fields.Many2one('ftiq.task.type', tracking=True)
    week_start = fields.Date(required=True, tracking=True)
    week_end = fields.Date(compute='_compute_week_end', store=True)
    note = fields.Text()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('returned', 'Returned'),
    ], default='draft', tracking=True)

    line_ids = fields.One2many('ftiq.weekly.plan.line', 'plan_id')
    project_id = fields.Many2one('project.project', string='Linked Project', copy=False, tracking=True)
    project_task_count = fields.Integer(compute='_compute_project_task_count')
    daily_task_count = fields.Integer(compute='_compute_daily_task_count')
    planned_count = fields.Integer(compute='_compute_stats', store=True)
    completed_count = fields.Integer(compute='_compute_stats', store=True)
    missed_count = fields.Integer(compute='_compute_stats', store=True)
    compliance_rate = fields.Float(compute='_compute_stats', store=True)

    @api.model
    def _default_team_id(self):
        return self._get_plannable_teams()[:1].id

    @api.model
    def _get_plannable_teams(self):
        Team = self.env['crm.team']
        user = self.env.user
        if self.env.su or user.has_group('ftiq_pharma_sfa.group_ftiq_manager'):
            return Team.search([])
        if user.has_group('ftiq_pharma_sfa.group_ftiq_supervisor'):
            return Team.search([('user_id', '=', user.id)])
        return Team.search([('member_ids', 'in', [user.id])])

    @api.model
    def _get_team_representatives(self, team):
        if not team:
            return self.env['res.users']
        members = team.member_ids.filtered(lambda member: not member.share)
        representatives = members.filtered('ftiq_is_medical_rep')
        return representatives or members

    @api.model
    def _is_placeholder_name(self, name):
        cleaned_name = (name or '').strip()
        if not cleaned_name:
            return True
        return cleaned_name in {'New Plan', _('New Plan')}

    @api.model
    def _build_plan_display_name(self, team=False, week_start=False, name=False):
        if not self._is_placeholder_name(name):
            return name.strip()
        team_name = team.display_name if team else _('No Team')
        date_value = fields.Date.to_date(week_start) if week_start else fields.Date.context_today(self)
        return _('%(team)s (%(date)s)') % {
            'team': team_name,
            'date': date_value,
        }

    def _build_project_display_name(self):
        self.ensure_one()
        return self._build_plan_display_name(self.team_id, self.week_start, self.name)

    @api.depends('line_ids.user_id')
    def _compute_user_id(self):
        for rec in self:
            reps = rec.line_ids.mapped('user_id')
            rec.user_id = reps[0] if len(reps) == 1 else False

    def _compute_allowed_team_ids(self):
        allowed_teams = self._get_plannable_teams()
        for rec in self:
            rec.allowed_team_ids = allowed_teams

    @api.depends('team_id')
    def _compute_allowed_user_ids(self):
        for rec in self:
            rec.allowed_user_ids = rec._get_team_representatives(rec.team_id)

    @api.depends('week_start')
    def _compute_week_end(self):
        for rec in self:
            rec.week_end = rec.week_start + timedelta(days=6) if rec.week_start else False

    @api.depends('line_ids.project_task_id')
    def _compute_project_task_count(self):
        for rec in self:
            rec.project_task_count = len(rec.line_ids.filtered('project_task_id'))

    @api.depends('line_ids.daily_task_id')
    def _compute_daily_task_count(self):
        for rec in self:
            rec.daily_task_count = len(rec.line_ids.filtered('daily_task_id'))

    @api.depends('line_ids.state')
    def _compute_stats(self):
        for rec in self:
            lines = rec.line_ids
            rec.planned_count = len(lines)
            rec.completed_count = len(lines.filtered(lambda l: l.state == 'completed'))
            rec.missed_count = len(lines.filtered(lambda l: l.state == 'missed'))
            rec.compliance_rate = (rec.completed_count / rec.planned_count * 100.0) if rec.planned_count else 0.0

    @api.onchange('team_id')
    def _onchange_team_id(self):
        for rec in self:
            allowed_users = rec._get_team_representatives(rec.team_id)
            for line in rec.line_ids:
                if line.user_id and line.user_id not in allowed_users:
                    line.user_id = False

    @api.constrains('team_id')
    def _check_team_access(self):
        for rec in self:
            rec._check_planning_access_for_team()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('team_id') and vals.get('user_id'):
                vals['team_id'] = self.env['res.users'].browse(vals['user_id']).sale_team_id.id
            if not vals.get('team_id'):
                default_team_id = self._default_team_id()
                if default_team_id:
                    vals['team_id'] = default_team_id
        records = super().create(vals_list)
        if not self.env.context.get('skip_assignment_notification'):
            records._notify_assignment()
        return records

    def write(self, vals):
        old_assignments = {rec.id: set(rec.line_ids.mapped('user_id').ids) for rec in self}
        result = super().write(vals)
        if ('line_ids' in vals or 'team_id' in vals) and not self.env.context.get('skip_assignment_notification'):
            changed = self.filtered(
                lambda rec: old_assignments.get(rec.id) != set(rec.line_ids.mapped('user_id').ids)
            )
            changed._notify_assignment(reassigned=True)
        if any(k in vals for k in ('name', 'week_start', 'team_id', 'line_ids', 'task_type_id', 'project_id')):
            self._sync_project_and_tasks(create_project=False, create_daily_tasks=False)
        return result

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.setdefault('name', _('%s (Copy)') % self.name)
        default.update({
            'state': 'draft',
            'project_id': False,
            'line_ids': [(5, 0, 0)],
        })
        new_plan = super().copy(default)
        for line in self.line_ids.sorted(key=lambda l: (l.sequence, l.id)):
            self.env['ftiq.weekly.plan.line'].create({
                'plan_id': new_plan.id,
                'user_id': line.user_id.id,
                'partner_id': line.partner_id.id,
                'scheduled_date': line.scheduled_date,
                'sequence': line.sequence,
                'note': line.note,
                'state': 'pending',
            })
        return new_plan

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft plans can be submitted.'))
            rec._validate_plan_setup()
            rec.state = 'submitted'
        self._sync_project_and_tasks(create_project=True, create_daily_tasks=True)

    def action_approve(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Only submitted plans can be approved.'))
            rec._validate_plan_setup()
            rec.state = 'approved'
        self._sync_project_and_tasks(create_project=True, create_daily_tasks=True)

    def action_return(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Only submitted plans can be returned.'))
            rec.state = 'returned'

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ('returned',):
                raise UserError(_('Can only reset returned plans to draft.'))
            rec.state = 'draft'

    def action_mark_missed(self):
        for rec in self:
            pending_lines = rec.line_ids.filtered(lambda line: line.state == 'pending')
            for line in pending_lines:
                if (
                    line.scheduled_date
                    and line.scheduled_date < fields.Date.today()
                    and (not line.visit_id or line.visit_id.state not in ('in_progress', 'submitted', 'approved'))
                ):
                    line.state = 'missed'

    def action_sync_project(self):
        self._validate_plan_setup()
        self._sync_project_and_tasks(create_project=True, create_daily_tasks=True)

    def action_open_project(self):
        self.ensure_one()
        if not self.project_id:
            self.action_sync_project()
        if not self.project_id:
            raise UserError(_('Project was not created.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Linked Project'),
            'res_model': 'project.project',
            'res_id': self.project_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_project_tasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Project Tasks'),
            'res_model': 'project.task',
            'view_mode': 'list,form,kanban,calendar,pivot,graph',
            'domain': [('ftiq_plan_id', '=', self.id)],
            'context': {
                'default_project_id': self.project_id.id,
                'default_ftiq_plan_id': self.id,
            },
        }

    def _notify_assignment(self, reassigned=False):
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        for rec in self.filtered('team_id'):
            assigned_users = rec.line_ids.mapped('user_id').filtered('partner_id')
            if not assigned_users:
                continue
            if reassigned:
                body = _(
                    'You have been assigned plan lines in <b>%s</b> for team <b>%s</b> '
                    '(week starting %s).'
                ) % (rec.name, rec.team_id.display_name, rec.week_start or '')
            else:
                body = _(
                    'New team plan assigned to you: <b>%s</b> for <b>%s</b> '
                    '(week starting %s).'
                ) % (rec.name, rec.team_id.display_name, rec.week_start or '')
            rec.message_post(
                body=body,
                partner_ids=assigned_users.mapped('partner_id').ids,
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
            )
            if activity_type:
                for assigned_user in assigned_users:
                    rec.activity_schedule(
                        activity_type_id=activity_type.id,
                        user_id=assigned_user.id,
                        summary=_('Weekly Plan Assignment'),
                        note=body,
                        date_deadline=rec.week_start or fields.Date.today(),
                    )

    def _sync_project_and_tasks(self, create_project=True, create_daily_tasks=True):
        Project = self.env['project.project'].with_context(
            mail_create_nosubscribe=True,
            tracking_disable=True,
        )
        Task = self.env['project.task'].with_context(
            mail_create_nosubscribe=True,
            tracking_disable=True,
        )
        DailyTask = self.env['ftiq.daily.task'].with_context(
            skip_assignment_notification=True,
            skip_project_task_sync=True,
            mail_create_nosubscribe=True,
            tracking_disable=True,
        )
        for rec in self:
            project = rec.project_id
            project_name = rec._build_project_display_name()
            if not project and create_project:
                project = Project.create({
                    'name': project_name,
                    'user_id': rec.supervisor_id.id or self.env.uid,
                    'company_id': self.env.company.id,
                })
                rec.project_id = project
            elif project:
                project.with_context(tracking_disable=True).write({
                    'name': project_name,
                    'user_id': rec.supervisor_id.id or self.env.uid,
                })

            project_task_map = {}
            project_task_lines = []
            project_task_values = []
            for line in rec.line_ids:
                assigned_user = line.user_id or rec.user_id
                task_vals = {
                    'name': _('%s - %s') % (line.partner_id.display_name, rec.name),
                    'partner_id': line.partner_id.id,
                    'date_deadline': self._line_deadline_datetime(line),
                    'planned_date_begin': self._line_datetime(line),
                    'description': line.note or rec.note or False,
                    'user_ids': [(6, 0, [assigned_user.id])] if assigned_user else False,
                    'ftiq_plan_id': rec.id,
                    'ftiq_plan_line_id': line.id,
                }
                if project:
                    task_vals['project_id'] = project.id
                if line.project_task_id and line.project_task_id.exists():
                    line.project_task_id.with_context(tracking_disable=True).write(task_vals)
                    project_task_map[line.id] = line.project_task_id
                elif project:
                    project_task_lines.append(line)
                    project_task_values.append(task_vals)
                else:
                    project_task_map[line.id] = False

            if project_task_values:
                created_project_tasks = Task.create(project_task_values)
                for line, project_task in zip(project_task_lines, created_project_tasks):
                    line.project_task_id = project_task
                    project_task_map[line.id] = project_task

            if not create_daily_tasks:
                continue

            daily_task_lines = []
            daily_task_values = []
            for line in rec.line_ids:
                assigned_user = line.user_id or rec.user_id
                project_task = project_task_map.get(line.id)
                daily_vals = {
                    'task_type': 'visit',
                    'partner_id': line.partner_id.id,
                    'associated_partner_id': line.partner_id.id,
                    'user_id': assigned_user.id if assigned_user else False,
                    'scheduled_date': self._line_datetime(line),
                    'priority': '1',
                    'description': line.note or rec.note or False,
                    'plan_id': rec.id,
                    'plan_line_id': line.id,
                    'project_id': project.id if project else False,
                    'project_task_id': project_task.id if project_task else False,
                }
                if line.daily_task_id and line.daily_task_id.exists():
                    line.daily_task_id.with_context(
                        skip_assignment_notification=True,
                        skip_project_task_sync=True,
                        tracking_disable=True,
                    ).write(daily_vals)
                    continue
                daily_task_lines.append(line)
                daily_task_values.append(daily_vals)

            if daily_task_values:
                created_daily_tasks = DailyTask.create(daily_task_values)
                for line, daily_task in zip(daily_task_lines, created_daily_tasks):
                    line.daily_task_id = daily_task

    def _check_planning_access_for_team(self):
        self.ensure_one()
        if self.env.su:
            return
        user = self.env.user
        if user.has_group('ftiq_pharma_sfa.group_ftiq_manager'):
            return
        if user.has_group('ftiq_pharma_sfa.group_ftiq_supervisor') and self.team_id and self.team_id.user_id != user:
            raise ValidationError(_('You can only create and manage plans for sales teams you lead.'))

    def _validate_plan_setup(self):
        for rec in self:
            rec._check_planning_access_for_team()
            if not rec.team_id:
                raise UserError(_('Select a sales team before saving or submitting the plan.'))
            if not rec.line_ids:
                raise UserError(_('Add at least one plan line before submitting the plan.'))
            missing_users = rec.line_ids.filtered(lambda line: not line.user_id)
            if missing_users:
                raise UserError(_('Each plan line must have a representative from the selected team.'))
            allowed_users = rec._get_team_representatives(rec.team_id)
            invalid_lines = rec.line_ids.filtered(lambda line: line.user_id not in allowed_users)
            if invalid_lines:
                raise UserError(_('Every plan line representative must belong to the selected sales team.'))

    @staticmethod
    def _line_datetime(line):
        plan_date = line.scheduled_date or fields.Date.today()
        return fields.Datetime.to_string(datetime.combine(plan_date, time(9, 0, 0)))

    @staticmethod
    def _line_deadline_datetime(line):
        plan_date = line.scheduled_date or fields.Date.today()
        return fields.Datetime.to_string(datetime.combine(plan_date, time(23, 59, 59)))


class FtiqWeeklyPlanLine(models.Model):
    _name = 'ftiq.weekly.plan.line'
    _description = 'Weekly Plan Line'
    _order = 'scheduled_date, sequence'

    plan_id = fields.Many2one('ftiq.weekly.plan', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', required=True)
    scheduled_date = fields.Date()
    day_of_week = fields.Selection(
        compute='_compute_day_of_week',
        store=True,
        selection=[
            ('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'),
            ('3', 'Thursday'), ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday'),
        ],
    )
    sequence = fields.Integer(default=10)
    note = fields.Text()
    visit_id = fields.Many2one('ftiq.visit', readonly=True)
    daily_task_id = fields.Many2one('ftiq.daily.task', string='Daily Task', copy=False, readonly=True)
    project_task_id = fields.Many2one('project.task', string='Project Task', copy=False, readonly=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('missed', 'Missed'),
    ], default='pending')

    team_id = fields.Many2one(related='plan_id.team_id', store=True, readonly=True)
    user_id = fields.Many2one('res.users', string='Representative')
    partner_specialty_id = fields.Many2one(related='partner_id.ftiq_specialty_id', store=True)
    partner_classification_id = fields.Many2one(related='partner_id.ftiq_classification_id', store=True)
    partner_area_id = fields.Many2one(related='partner_id.ftiq_area_id', store=True)

    @api.depends('scheduled_date')
    def _compute_day_of_week(self):
        for rec in self:
            rec.day_of_week = str(rec.scheduled_date.weekday()) if rec.scheduled_date else False

    @api.constrains('plan_id', 'team_id', 'user_id')
    def _check_representative_team_membership(self):
        for rec in self:
            if not rec.plan_id or not rec.team_id or not rec.user_id:
                continue
            allowed_users = rec.plan_id._get_team_representatives(rec.team_id)
            if rec.user_id not in allowed_users:
                raise ValidationError(_(
                    'Representative %(rep)s is not a member of team %(team)s.'
                ) % {
                    'rep': rec.user_id.display_name,
                    'team': rec.team_id.display_name,
                })

    def action_create_visit(self):
        self.ensure_one()
        if self.visit_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'ftiq.visit',
                'res_id': self.visit_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        if self.plan_id.state != 'approved':
            raise UserError(_('Visits can only be created from approved plans.'))
        if not self.user_id:
            raise UserError(_('Assign a representative on the plan line before creating the visit.'))
        visit = self.env['ftiq.visit'].create({
            'partner_id': self.partner_id.id,
            'user_id': self.user_id.id,
            'plan_line_id': self.id,
            'visit_date': self.scheduled_date or fields.Date.today(),
            'attendance_id': self._find_attendance(),
        })
        vals = {'visit_id': visit.id}
        if self.daily_task_id:
            task_vals = {'visit_id': visit.id}
            if self.daily_task_id.state == 'pending':
                task_vals['state'] = 'in_progress'
            self.daily_task_id.write(task_vals)
        self.write(vals)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ftiq.visit',
            'res_id': visit.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _find_attendance(self):
        att = self.env['ftiq.field.attendance'].search([
            ('user_id', '=', self.user_id.id),
            ('date', '=', fields.Date.today()),
            ('state', '=', 'checked_in'),
        ], limit=1)
        return att.id if att else False
