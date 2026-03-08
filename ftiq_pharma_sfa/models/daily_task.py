from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FtiqDailyTask(models.Model):
    _name = 'ftiq.daily.task'
    _description = 'Daily Task'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scheduled_date desc, priority desc, id desc'

    name = fields.Char(string='Reference', readonly=True, copy=False, default='New')
    task_type = fields.Selection([
        ('visit', 'Visit'),
        ('order', 'Order'),
        ('delivery', 'Delivery'),
        ('collection', 'Collection'),
        ('stock', 'Stock Check'),
        ('report', 'Report'),
        ('other', 'Other'),
    ], string='Task Type', required=True, default='visit', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Client', required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Representative', default=lambda self: self.env.uid, tracking=True)
    team_id = fields.Many2one('crm.team', string='Sales Team', compute='_compute_team_id', store=True, readonly=True)
    supervisor_id = fields.Many2one('res.users', string='Supervisor', related='team_id.user_id', store=True)
    scheduled_date = fields.Datetime(string='Scheduled Date', required=True, tracking=True)
    completed_date = fields.Datetime(string='Completed Date')
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Important'),
        ('2', 'Urgent'),
    ], string='Priority', default='0')
    description = fields.Text(string='Description')
    outcome = fields.Text(string='Outcome / Result')
    visit_id = fields.Many2one('ftiq.visit', string='Created Visit')
    sale_order_id = fields.Many2one('sale.order', string='Created Sale Order')
    payment_id = fields.Many2one('account.payment', string='Created Payment')
    stock_check_id = fields.Many2one('ftiq.stock.check', string='Created Stock Check')
    plan_id = fields.Many2one('ftiq.weekly.plan', string='Weekly Plan', copy=False)
    plan_line_id = fields.Many2one('ftiq.weekly.plan.line', string='Plan Line', copy=False)
    project_id = fields.Many2one('project.project', string='Project', tracking=True)
    project_task_id = fields.Many2one('project.task', string='Project Task', copy=False)
    photo_1 = fields.Binary(string='Photo 1', attachment=True)
    photo_2 = fields.Binary(string='Photo 2', attachment=True)
    photo_3 = fields.Binary(string='Photo 3', attachment=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='pending', tracking=True)
    latitude = fields.Float(string='Latitude', digits=(10, 7))
    longitude = fields.Float(string='Longitude', digits=(10, 7))
    tag_ids = fields.Many2many('ftiq.task.type', string='Tags')
    associated_partner_id = fields.Many2one('res.partner', string='Associated Client')

    @api.depends('plan_line_id.team_id', 'plan_id.team_id', 'user_id.sale_team_id')
    def _compute_team_id(self):
        for rec in self:
            rec.team_id = rec.plan_line_id.team_id or rec.plan_id.team_id or rec.user_id.sale_team_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('ftiq.daily.task') or 'New'
            if vals.get('project_task_id') and not vals.get('project_id'):
                task = self.env['project.task'].browse(vals['project_task_id'])
                vals['project_id'] = task.project_id.id
        records = super().create(vals_list)
        if not self.env.context.get('skip_assignment_notification'):
            records._notify_assignment()
        if not self.env.context.get('skip_project_task_sync'):
            records._sync_project_task(create_missing=True)
        return records

    def write(self, vals):
        old_user = {rec.id: rec.user_id.id for rec in self}
        result = super().write(vals)
        if 'user_id' in vals and not self.env.context.get('skip_assignment_notification'):
            changed = self.filtered(lambda rec: old_user.get(rec.id) != rec.user_id.id)
            changed._notify_assignment(reassigned=True)
        if any(k in vals for k in (
            'name', 'task_type', 'partner_id', 'user_id', 'scheduled_date',
            'description', 'project_id', 'project_task_id', 'plan_id', 'plan_line_id',
        )) and not self.env.context.get('skip_project_task_sync'):
            self._sync_project_task(create_missing=False)
        return result

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_complete(self):
        for rec in self:
            rec._validate_completion_dependencies()
        self.write({
            'state': 'completed',
            'completed_date': fields.Datetime.now(),
        })

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset(self):
        self.write({'state': 'pending', 'completed_date': False})

    def action_create_visit(self):
        self.ensure_one()
        if self.visit_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Visit'),
                'res_model': 'ftiq.visit',
                'res_id': self.visit_id.id,
                'view_mode': 'form',
            }
        attendance = self._find_attendance_for(self.user_id.id)
        visit = self.env['ftiq.visit'].create({
            'partner_id': self.partner_id.id,
            'user_id': self.user_id.id,
            'visit_date': fields.Datetime.to_datetime(self.scheduled_date).date() if self.scheduled_date else fields.Date.context_today(self),
            'plan_line_id': self.plan_line_id.id,
            'attendance_id': attendance.id if attendance else False,
        })
        vals = {'visit_id': visit.id}
        if self.state == 'pending':
            vals['state'] = 'in_progress'
        self.write(vals)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Visit'),
            'res_model': 'ftiq.visit',
            'res_id': visit.id,
            'view_mode': 'form',
        }

    def action_create_order(self):
        self.ensure_one()
        if self.sale_order_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Sale Order'),
                'res_model': 'sale.order',
                'res_id': self.sale_order_id.id,
                'view_mode': 'form',
            }
        attendance = self.visit_id.attendance_id or self._find_attendance_for(self.user_id.id)
        order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'user_id': self.user_id.id,
            'is_field_order': True,
            'ftiq_visit_id': self.visit_id.id if self.visit_id else False,
            'ftiq_attendance_id': attendance.id if attendance else False,
            'ftiq_latitude': self.visit_id.start_latitude or self.latitude,
            'ftiq_longitude': self.visit_id.start_longitude or self.longitude,
            'ftiq_daily_task_id': self.id,
        })
        self.sale_order_id = order.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Order'),
            'res_model': 'sale.order',
            'res_id': order.id,
            'view_mode': 'form',
        }

    def action_create_collection(self):
        self.ensure_one()
        if self.payment_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Payment'),
                'res_model': 'account.payment',
                'res_id': self.payment_id.id,
                'view_mode': 'form',
            }
        attendance = self.visit_id.attendance_id or self._find_attendance_for(self.user_id.id)
        payment = self.env['account.payment'].create({
            'partner_id': self.partner_id.id,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'is_field_collection': True,
            'ftiq_user_id': self.user_id.id,
            'ftiq_visit_id': self.visit_id.id if self.visit_id else False,
            'ftiq_attendance_id': attendance.id if attendance else False,
            'ftiq_latitude': self.visit_id.start_latitude or self.latitude,
            'ftiq_longitude': self.visit_id.start_longitude or self.longitude,
            'ftiq_daily_task_id': self.id,
        })
        self.payment_id = payment.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payment'),
            'res_model': 'account.payment',
            'res_id': payment.id,
            'view_mode': 'form',
        }

    def action_create_stock_check(self):
        self.ensure_one()
        if self.stock_check_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Stock Check'),
                'res_model': 'ftiq.stock.check',
                'res_id': self.stock_check_id.id,
                'view_mode': 'form',
            }
        attendance = self.visit_id.attendance_id or self._find_attendance_for(self.user_id.id)
        check = self.env['ftiq.stock.check'].create({
            'partner_id': self.partner_id.id,
            'user_id': self.user_id.id,
            'visit_id': self.visit_id.id if self.visit_id else False,
            'attendance_id': attendance.id if attendance else False,
            'latitude': self.visit_id.end_latitude or self.visit_id.start_latitude or self.latitude,
            'longitude': self.visit_id.end_longitude or self.visit_id.start_longitude or self.longitude,
            'ftiq_daily_task_id': self.id,
        })
        self.stock_check_id = check.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Stock Check'),
            'res_model': 'ftiq.stock.check',
            'res_id': check.id,
            'view_mode': 'form',
        }

    def action_create_project_task(self):
        self.ensure_one()
        self._sync_project_task(create_missing=True)
        return self.action_open_project_task()

    def action_open_project_task(self):
        self.ensure_one()
        if not self.project_task_id:
            self._sync_project_task(create_missing=True)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Project Task'),
            'res_model': 'project.task',
            'res_id': self.project_task_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _notify_assignment(self, reassigned=False):
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        for rec in self.filtered('user_id'):
            if not rec.user_id.partner_id:
                continue
            if reassigned:
                body = _(
                    'Task <b>%s</b> was reassigned to you for %s.'
                ) % (rec.name, rec.scheduled_date or '')
            else:
                body = _(
                    'New task assigned to you: <b>%s</b> scheduled on %s.'
                ) % (rec.name, rec.scheduled_date or '')
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
                    summary=_('Daily Task Assignment'),
                    note=body,
                    date_deadline=fields.Date.to_date(rec.scheduled_date) or fields.Date.today(),
                )

    def _sync_project_task(self, create_missing=False):
        Task = self.env['project.task']
        for rec in self:
            if rec.project_task_id and rec.project_task_id.exists() and not rec.project_id:
                rec.project_id = rec.project_task_id.project_id
            if not rec.project_id:
                continue
            vals = {
                'name': rec.name if rec.name and rec.name != 'New' else _('%s Task') % (rec.task_profile_id.display_name or rec.task_type),
                'project_id': rec.project_id.id,
                'partner_id': rec.partner_id.id,
                'date_deadline': self._task_deadline_datetime(rec.scheduled_date),
                'planned_date_begin': rec.scheduled_date,
                'description': rec.description or False,
                'user_ids': [(6, 0, [rec.user_id.id])] if rec.user_id else False,
                'ftiq_daily_task_id': rec.id,
                'ftiq_plan_id': rec.plan_id.id if rec.plan_id else False,
                'ftiq_plan_line_id': rec.plan_line_id.id if rec.plan_line_id else False,
            }
            if rec.project_task_id and rec.project_task_id.exists():
                rec.project_task_id.write(vals)
            elif create_missing:
                rec.project_task_id = Task.create(vals)

    @staticmethod
    def _task_deadline_datetime(dt_value):
        if not dt_value:
            return False
        dt = fields.Datetime.to_datetime(dt_value)
        if not dt:
            return False
        return fields.Datetime.to_string(dt.replace(hour=23, minute=59, second=59, microsecond=0))

    @api.model
    def _find_attendance_for(self, user_id):
        if not user_id:
            return self.env['ftiq.field.attendance']
        return self.env['ftiq.field.attendance'].search([
            ('user_id', '=', user_id),
            ('date', '=', fields.Date.context_today(self)),
            ('state', '=', 'checked_in'),
        ], limit=1)

    def _validate_completion_dependencies(self):
        self.ensure_one()
        if self.task_type == 'visit':
            if not self.visit_id or self.visit_id.state != 'approved':
                raise UserError(_('Visit tasks can only be completed after the linked visit is approved.'))
        elif self.task_type == 'order':
            if not self.sale_order_id or self.sale_order_id.state not in ('sale', 'done'):
                raise UserError(_('Order tasks can only be completed after the linked order is confirmed.'))
        elif self.task_type == 'collection':
            if not self.payment_id or self.payment_id.state not in ('in_process', 'paid'):
                raise UserError(_('Collection tasks can only be completed after the linked collection is posted.'))
        elif self.task_type == 'stock':
            if not self.stock_check_id or self.stock_check_id.state != 'reviewed':
                raise UserError(_('Stock tasks can only be completed after the stock check is reviewed.'))
