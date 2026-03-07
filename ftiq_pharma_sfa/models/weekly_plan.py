from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FtiqWeeklyPlan(models.Model):
    _name = 'ftiq.weekly.plan'
    _description = 'Weekly Visit Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'week_start desc'

    name = fields.Char(required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Representative', required=True, tracking=True)
    supervisor_id = fields.Many2one(
        'res.users',
        string='Created By',
        default=lambda self: self.env.uid,
        readonly=True,
    )
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

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._notify_assignment()
        return records

    def write(self, vals):
        old_user = {rec.id: rec.user_id.id for rec in self}
        result = super().write(vals)
        if 'user_id' in vals:
            changed = self.filtered(lambda rec: old_user.get(rec.id) != rec.user_id.id)
            changed._notify_assignment(reassigned=True)
        if any(k in vals for k in ('name', 'week_start', 'user_id', 'line_ids', 'task_type_id', 'project_id')):
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
            rec.state = 'submitted'
        self._sync_project_and_tasks(create_project=True, create_daily_tasks=True)

    def action_approve(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Only submitted plans can be approved.'))
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
                if line.scheduled_date and line.scheduled_date < fields.Date.today():
                    line.state = 'missed'

    def action_sync_project(self):
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
        for rec in self.filtered('user_id'):
            if not rec.user_id.partner_id:
                continue
            if reassigned:
                body = _(
                    'You have been assigned as representative for plan <b>%s</b> '
                    '(week starting %s).'
                ) % (rec.name, rec.week_start or '')
            else:
                body = _(
                    'New plan assigned to you: <b>%s</b> (week starting %s).'
                ) % (rec.name, rec.week_start or '')
            rec.message_post(
                body=body,
                partner_ids=[rec.user_id.partner_id.id],
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
            )
            if activity_type:
                rec.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=rec.user_id.id,
                    summary=_('Weekly Plan Assignment'),
                    note=body,
                    date_deadline=rec.week_start or fields.Date.today(),
                )

    def _sync_project_and_tasks(self, create_project=True, create_daily_tasks=True):
        Task = self.env['project.task']
        DailyTask = self.env['ftiq.daily.task']
        for rec in self:
            project = rec.project_id
            if not project and create_project:
                project = self.env['project.project'].create({
                    'name': _('Plan %s (%s)') % (rec.name, rec.week_start or ''),
                    'user_id': rec.user_id.id,
                    'company_id': self.env.company.id,
                })
                rec.project_id = project
            elif project:
                project.write({
                    'name': _('Plan %s (%s)') % (rec.name, rec.week_start or ''),
                    'user_id': rec.user_id.id,
                })

            for line in rec.line_ids:
                task_vals = {
                    'name': _('%s - %s') % (line.partner_id.display_name, rec.name),
                    'partner_id': line.partner_id.id,
                    'date_deadline': self._line_deadline_datetime(line),
                    'planned_date_begin': self._line_datetime(line),
                    'description': line.note or rec.note or False,
                    'user_ids': [(6, 0, [rec.user_id.id])] if rec.user_id else False,
                    'ftiq_plan_id': rec.id,
                    'ftiq_plan_line_id': line.id,
                }
                if project:
                    task_vals['project_id'] = project.id
                if line.project_task_id and line.project_task_id.exists():
                    line.project_task_id.write(task_vals)
                    project_task = line.project_task_id
                elif project:
                    project_task = Task.create(task_vals)
                    line.project_task_id = project_task
                else:
                    project_task = False

                if not create_daily_tasks:
                    continue
                daily_vals = {
                    'task_type': 'visit',
                    'partner_id': line.partner_id.id,
                    'associated_partner_id': line.partner_id.id,
                    'user_id': rec.user_id.id,
                    'scheduled_date': self._line_datetime(line),
                    'priority': '1',
                    'description': line.note or rec.note or False,
                    'plan_id': rec.id,
                    'plan_line_id': line.id,
                    'project_id': project.id if project else False,
                    'project_task_id': project_task.id if project_task else False,
                }
                if line.daily_task_id and line.daily_task_id.exists():
                    line.daily_task_id.write(daily_vals)
                else:
                    line.daily_task_id = DailyTask.create(daily_vals)

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

    user_id = fields.Many2one(related='plan_id.user_id', store=True)
    partner_specialty_id = fields.Many2one(related='partner_id.ftiq_specialty_id', store=True)
    partner_classification_id = fields.Many2one(related='partner_id.ftiq_classification_id', store=True)
    partner_area_id = fields.Many2one(related='partner_id.ftiq_area_id', store=True)

    @api.depends('scheduled_date')
    def _compute_day_of_week(self):
        for rec in self:
            rec.day_of_week = str(rec.scheduled_date.weekday()) if rec.scheduled_date else False

    def action_create_visit(self):
        self.ensure_one()
        if self.visit_id:
            raise UserError(_('A visit already exists for this plan line.'))
        visit = self.env['ftiq.visit'].create({
            'partner_id': self.partner_id.id,
            'user_id': self.user_id.id,
            'plan_line_id': self.id,
            'visit_date': self.scheduled_date or fields.Date.today(),
            'attendance_id': self._find_attendance(),
        })
        vals = {'visit_id': visit.id, 'state': 'completed'}
        if self.daily_task_id:
            self.daily_task_id.write({
                'visit_id': visit.id,
                'state': 'completed',
                'completed_date': fields.Datetime.now(),
            })
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
