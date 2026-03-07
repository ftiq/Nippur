from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FtiqVisit(models.Model):
    _name = 'ftiq.visit'
    _description = 'Doctor/Center Visit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'visit_date desc, id desc'

    name = fields.Char(readonly=True, default='New', copy=False)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.uid, required=True, tracking=True)
    team_id = fields.Many2one('crm.team', compute='_compute_team_id', store=True, readonly=True)
    partner_id = fields.Many2one('res.partner', required=True, tracking=True)
    attendance_id = fields.Many2one('ftiq.field.attendance')
    plan_line_id = fields.Many2one('ftiq.weekly.plan.line')
    is_planned = fields.Boolean(compute='_compute_is_planned', store=True)
    unplanned_reason = fields.Char()

    visit_date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    start_time = fields.Datetime()
    end_time = fields.Datetime()
    duration = fields.Float(compute='_compute_duration', store=True)

    start_latitude = fields.Float(digits=(10, 7))
    start_longitude = fields.Float(digits=(10, 7))
    start_accuracy = fields.Float(string='Start Accuracy (m)')
    end_latitude = fields.Float(digits=(10, 7))
    end_longitude = fields.Float(digits=(10, 7))
    end_accuracy = fields.Float(string='End Accuracy (m)')

    outcome = fields.Selection([
        ('interested', 'Interested'),
        ('not_interested', 'Not Interested'),
        ('follow_up', 'Follow Up Required'),
        ('sample_requested', 'Sample Requested'),
    ], tracking=True)
    general_feedback = fields.Text()

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('returned', 'Returned'),
    ], default='draft', tracking=True)

    product_line_ids = fields.One2many('ftiq.visit.product.line', 'visit_id')
    material_view_log_ids = fields.One2many('ftiq.material.view.log', 'visit_id')

    photo_1 = fields.Binary(string='Photo 1', attachment=True)
    photo_2 = fields.Binary(string='Photo 2', attachment=True)
    photo_3 = fields.Binary(string='Photo 3', attachment=True)
    signature = fields.Binary(string='Client Signature')

    partner_specialty_id = fields.Many2one(related='partner_id.ftiq_specialty_id', store=True)
    partner_classification_id = fields.Many2one(related='partner_id.ftiq_classification_id', store=True)
    partner_area_id = fields.Many2one(related='partner_id.ftiq_area_id', store=True)

    sale_order_ids = fields.One2many('sale.order', 'ftiq_visit_id', string='Field Orders')
    payment_ids = fields.One2many('account.payment', 'ftiq_visit_id', string='Collections')
    invoice_ids = fields.One2many('account.move', 'ftiq_visit_id', string='Invoices')
    stock_check_ids = fields.One2many('ftiq.stock.check', 'visit_id', string='Stock Checks')

    sale_order_count = fields.Integer(compute='_compute_related_counts')
    payment_count = fields.Integer(compute='_compute_related_counts')
    stock_check_count = fields.Integer(compute='_compute_related_counts')

    @api.depends('plan_line_id.team_id', 'user_id.sale_team_id')
    def _compute_team_id(self):
        for rec in self:
            rec.team_id = rec.plan_line_id.team_id or rec.user_id.sale_team_id

    def _compute_related_counts(self):
        sale_order_obj = self.env['sale.order'].sudo()
        payment_obj = self.env['account.payment'].sudo()
        stock_check_obj = self.env['ftiq.stock.check'].sudo()
        for rec in self:
            rec.sale_order_count = sale_order_obj.search_count([
                ('ftiq_visit_id', '=', rec.id),
            ])
            rec.payment_count = payment_obj.search_count([
                ('ftiq_visit_id', '=', rec.id),
            ])
            rec.stock_check_count = stock_check_obj.search_count([
                ('visit_id', '=', rec.id),
            ])

    @api.depends('plan_line_id')
    def _compute_is_planned(self):
        for rec in self:
            rec.is_planned = bool(rec.plan_line_id)

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for rec in self:
            if rec.start_time and rec.end_time:
                delta = rec.end_time - rec.start_time
                rec.duration = delta.total_seconds() / 3600.0
            else:
                rec.duration = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('ftiq.visit') or 'New'
            plan_line = self.env['ftiq.weekly.plan.line'].browse(vals.get('plan_line_id'))
            if plan_line:
                vals.setdefault('user_id', plan_line.user_id.id)
                vals.setdefault('partner_id', plan_line.partner_id.id)
                vals.setdefault('visit_date', plan_line.scheduled_date or fields.Date.context_today(self))
            if not vals.get('attendance_id') and vals.get('user_id'):
                attendance = self._find_active_attendance(
                    vals['user_id'],
                    vals.get('visit_date') or fields.Date.context_today(self),
                )
                if attendance:
                    vals['attendance_id'] = attendance.id
        records = super().create(vals_list)
        records._sync_plan_line_progress()
        return records

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.update({
            'name': 'New',
            'state': 'draft',
            'attendance_id': False,
            'plan_line_id': False,
            'start_time': False,
            'end_time': False,
            'start_latitude': 0.0,
            'start_longitude': 0.0,
            'end_latitude': 0.0,
            'end_longitude': 0.0,
            'product_line_ids': [(5, 0, 0)],
            'material_view_log_ids': [(5, 0, 0)],
        })
        new_visit = super().copy(default)
        line_map = {}
        for line in self.product_line_ids.sorted(key=lambda l: (l.sequence, l.id)):
            new_line = self.env['ftiq.visit.product.line'].create({
                'visit_id': new_visit.id,
                'product_id': line.product_id.id,
                'call_reason_id': line.call_reason_id.id,
                'detail_notes': line.detail_notes,
                'outcome': line.outcome,
                'samples_distributed': line.samples_distributed,
                'stock_on_hand': line.stock_on_hand,
                'feedback': line.feedback,
                'sequence': line.sequence,
            })
            line_map[line.id] = new_line.id
        for log in self.material_view_log_ids:
            self.env['ftiq.material.view.log'].create({
                'visit_id': new_visit.id,
                'product_line_id': line_map.get(log.product_line_id.id),
                'material_id': log.material_id.id,
                'start_time': log.start_time,
                'end_time': log.end_time,
            })
        return new_visit

    def action_start(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Visit can only be started from draft state.'))
        ctx = self.env.context
        lat = ctx.get('ftiq_latitude', 0)
        lng = ctx.get('ftiq_longitude', 0)
        if not lat or not lng:
            raise UserError(_('Location is required to start a visit. Enable location services and try again.'))
        if ctx.get('ftiq_is_mock'):
            raise UserError(_('Mock location detected. Fake GPS applications are not allowed.'))
        attendance = self.attendance_id
        if not attendance or attendance.state != 'checked_in':
            attendance = self._find_active_attendance(self.user_id.id, self.visit_date or fields.Date.context_today(self))
        if not attendance:
            attendance = self.env['ftiq.field.attendance'].ensure_operation_attendance(
                self.user_id.id,
                attendance_date=self.visit_date or fields.Date.context_today(self),
                latitude=lat,
                longitude=lng,
                accuracy=ctx.get('ftiq_accuracy', 0),
                is_mock=ctx.get('ftiq_is_mock', False),
                entry_reference=f'{self._name},{self.id}',
            )
        vals = {
            'state': 'in_progress',
            'attendance_id': attendance.id,
            'start_time': fields.Datetime.now(),
            'start_latitude': lat,
            'start_longitude': lng,
            'start_accuracy': ctx.get('ftiq_accuracy', 0),
        }
        self.write(vals)
        self._sync_plan_line_progress()

    def action_end(self):
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_('Visit must be in progress to end it.'))
        ctx = self.env.context
        lat = ctx.get('ftiq_latitude', 0)
        lng = ctx.get('ftiq_longitude', 0)
        if not lat or not lng:
            raise UserError(_('GPS location is required to end a visit. Please enable location services.'))
        if ctx.get('ftiq_is_mock'):
            raise UserError(_('Mock location detected. Fake GPS applications are not allowed.'))
        vals = {
            'end_time': fields.Datetime.now(),
            'end_latitude': lat,
            'end_longitude': lng,
            'end_accuracy': ctx.get('ftiq_accuracy', 0),
        }
        self.write(vals)

    def action_submit(self):
        self.ensure_one()
        if self.state not in ('in_progress', 'returned'):
            raise UserError(_('Cannot submit from current state.'))
        self._validate_submission()
        self.write({'state': 'submitted'})
        self._sync_plan_line_progress()

    def action_approve(self):
        self.ensure_one()
        if self.state != 'submitted':
            raise UserError(_('Only submitted visits can be approved.'))
        self.write({'state': 'approved'})
        self._sync_plan_line_progress()

    def action_return(self):
        self.ensure_one()
        if self.state != 'submitted':
            raise UserError(_('Only submitted visits can be returned.'))
        self.write({'state': 'returned'})
        self._sync_plan_line_progress()

    def action_reset_draft(self):
        self.ensure_one()
        if self.state not in ('returned',):
            raise UserError(_('Can only reset returned visits to draft.'))
        self.write({'state': 'draft'})
        self._sync_plan_line_progress()

    def action_show_on_map(self):
        self.ensure_one()
        lat = self.start_latitude or self.end_latitude
        lng = self.start_longitude or self.end_longitude
        if not lat or not lng:
            raise UserError(_('No GPS coordinates recorded for this visit.'))
        url = 'https://www.google.com/maps?q=%s,%s' % (lat, lng)
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    def action_create_sale_order(self):
        self.ensure_one()
        self._ensure_execution_started()
        order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'user_id': self.user_id.id,
            'is_field_order': True,
            'ftiq_visit_id': self.id,
            'ftiq_attendance_id': self.attendance_id.id if self.attendance_id else False,
            'ftiq_latitude': self.start_latitude,
            'ftiq_longitude': self.start_longitude,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Field Order'),
            'res_model': 'sale.order',
            'res_id': order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_payment(self):
        self.ensure_one()
        self._ensure_execution_started()
        payment = self.env['account.payment'].create({
            'partner_id': self.partner_id.id,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'is_field_collection': True,
            'ftiq_user_id': self.user_id.id,
            'ftiq_visit_id': self.id,
            'ftiq_attendance_id': self.attendance_id.id if self.attendance_id else False,
            'ftiq_latitude': self.start_latitude,
            'ftiq_longitude': self.start_longitude,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cash Collection'),
            'res_model': 'account.payment',
            'res_id': payment.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_stock_check(self):
        self.ensure_one()
        self._ensure_execution_started()
        check = self.env['ftiq.stock.check'].create({
            'partner_id': self.partner_id.id,
            'user_id': self.user_id.id,
            'visit_id': self.id,
            'attendance_id': self.attendance_id.id if self.attendance_id else False,
            'latitude': self.end_latitude or self.start_latitude,
            'longitude': self.end_longitude or self.start_longitude,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Stock Check'),
            'res_model': 'ftiq.stock.check',
            'res_id': check.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_sale_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Field Orders'),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('ftiq_visit_id', '=', self.id)],
            'context': {'default_ftiq_visit_id': self.id, 'default_partner_id': self.partner_id.id, 'default_is_field_order': True},
        }

    def action_view_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Collections'),
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('ftiq_visit_id', '=', self.id)],
            'context': {'default_ftiq_visit_id': self.id, 'default_partner_id': self.partner_id.id, 'default_is_field_collection': True},
        }

    def action_view_stock_checks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Stock Checks'),
            'res_model': 'ftiq.stock.check',
            'view_mode': 'list,form',
            'domain': [('visit_id', '=', self.id)],
            'context': {'default_visit_id': self.id, 'default_partner_id': self.partner_id.id},
        }

    @api.model
    def _find_active_attendance(self, user_id, visit_date):
        if not user_id or not visit_date:
            return self.env['ftiq.field.attendance']
        visit_date = fields.Date.to_date(visit_date)
        return self.env['ftiq.field.attendance'].search([
            ('user_id', '=', user_id),
            ('date', '=', visit_date),
            ('state', '=', 'checked_in'),
        ], limit=1)

    def _ensure_execution_started(self):
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_('The visit must be in progress before creating linked field operations.'))

    def _validate_submission(self):
        self.ensure_one()
        if not self.start_time:
            raise UserError(_('Start the visit before submitting it.'))
        if not self.end_time:
            raise UserError(_('End the visit before submitting it.'))
        if self.end_time < self.start_time:
            raise UserError(_('Visit end time cannot be earlier than the start time.'))
        if not self.duration:
            raise UserError(_('Visit duration must be greater than zero before submission.'))
        if not (self.start_latitude and self.start_longitude and self.end_latitude and self.end_longitude):
            raise UserError(_('Both start and end GPS coordinates are required before submission.'))
        if not self.outcome:
            raise UserError(_('Select a visit outcome before submission.'))
        if not self.is_planned and not self.unplanned_reason:
            raise UserError(_('An unplanned visit reason is required before submission.'))
        has_execution_evidence = any((
            self.general_feedback,
            self.product_line_ids,
            self.material_view_log_ids,
            self.sale_order_ids,
            self.payment_ids,
            self.stock_check_ids,
            self.photo_1,
            self.photo_2,
            self.photo_3,
            self.signature,
        ))
        if not has_execution_evidence:
            raise UserError(_(
                'Add execution evidence before submission. '
                'Use feedback, product details, linked operations, photos, or a signature.'
            ))

    def _sync_plan_line_progress(self):
        for rec in self.filtered('plan_line_id'):
            plan_line = rec.plan_line_id
            task = plan_line.daily_task_id
            plan_vals = {}
            task_vals = {}
            if plan_line.visit_id != rec:
                plan_vals['visit_id'] = rec.id
            if task and task.visit_id != rec:
                task_vals['visit_id'] = rec.id

            if rec.state == 'approved':
                if plan_line.state != 'completed':
                    plan_vals['state'] = 'completed'
                if task and task.state not in ('completed', 'cancelled'):
                    task_vals.update({
                        'state': 'completed',
                        'completed_date': rec.end_time or fields.Datetime.now(),
                    })
            else:
                if plan_line.state in ('completed', 'missed'):
                    plan_vals['state'] = 'pending'
                if task and task.state not in ('completed', 'cancelled') and rec.state in ('in_progress', 'submitted', 'returned'):
                    task_vals.setdefault('state', 'in_progress')
                if task and task.state == 'completed' and rec.state != 'approved':
                    task_vals.update({
                        'state': 'pending',
                        'completed_date': False,
                    })

            if plan_vals:
                plan_line.write(plan_vals)
            if task_vals:
                task.write(task_vals)


class FtiqVisitProductLine(models.Model):
    _name = 'ftiq.visit.product.line'
    _description = 'Visit Product Line'
    _order = 'sequence, id'

    visit_id = fields.Many2one('ftiq.visit', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', required=True)
    call_reason_id = fields.Many2one('ftiq.call.reason')
    detail_notes = fields.Text()
    outcome = fields.Selection([
        ('interested', 'Interested'),
        ('not_interested', 'Not Interested'),
        ('follow_up', 'Follow Up Required'),
        ('sample_requested', 'Sample Requested'),
    ])
    samples_distributed = fields.Integer(default=0)
    stock_on_hand = fields.Integer(default=0)
    feedback = fields.Text()
    sequence = fields.Integer(default=10)

    user_id = fields.Many2one(related='visit_id.user_id', store=True)
    visit_date = fields.Date(related='visit_id.visit_date', store=True)
    partner_id = fields.Many2one(related='visit_id.partner_id', store=True)


class FtiqMaterialViewLog(models.Model):
    _name = 'ftiq.material.view.log'
    _description = 'Material View Log'
    _order = 'start_time desc'

    visit_id = fields.Many2one('ftiq.visit', required=True, ondelete='cascade')
    product_line_id = fields.Many2one('ftiq.visit.product.line', ondelete='set null')
    material_id = fields.Many2one('ftiq.marketing.material', required=True)
    product_id = fields.Many2one(related='material_id.product_id', store=True)
    user_id = fields.Many2one(related='visit_id.user_id', store=True)
    start_time = fields.Datetime()
    end_time = fields.Datetime()
    duration = fields.Float(compute='_compute_duration', store=True)

    MAX_DURATION_MINUTES = 10

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for rec in self:
            if rec.start_time and rec.end_time:
                delta = rec.end_time - rec.start_time
                minutes = delta.total_seconds() / 60.0
                if minutes > self.MAX_DURATION_MINUTES:
                    minutes = self.MAX_DURATION_MINUTES
                rec.duration = minutes
            else:
                rec.duration = 0.0
