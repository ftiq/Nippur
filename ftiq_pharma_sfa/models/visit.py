from odoo import models, fields, api, _
from odoo.exceptions import UserError


class FtiqVisit(models.Model):
    _name = 'ftiq.visit'
    _description = 'Doctor/Center Visit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'visit_date desc, id desc'

    name = fields.Char(readonly=True, default='New', copy=False)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.uid, required=True, tracking=True)
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
    end_latitude = fields.Float(digits=(10, 7))
    end_longitude = fields.Float(digits=(10, 7))

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
        records = super().create(vals_list)
        for rec in records:
            if rec.plan_line_id and rec.plan_line_id.state == 'pending':
                rec.plan_line_id.write({'visit_id': rec.id, 'state': 'completed'})
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
        vals = {'state': 'in_progress', 'start_time': fields.Datetime.now()}
        ctx = self.env.context
        if ctx.get('ftiq_latitude'):
            vals['start_latitude'] = ctx['ftiq_latitude']
        if ctx.get('ftiq_longitude'):
            vals['start_longitude'] = ctx['ftiq_longitude']
        self.write(vals)

    def action_end(self):
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_('Visit must be in progress to end it.'))
        vals = {'end_time': fields.Datetime.now()}
        ctx = self.env.context
        if ctx.get('ftiq_latitude'):
            vals['end_latitude'] = ctx['ftiq_latitude']
        if ctx.get('ftiq_longitude'):
            vals['end_longitude'] = ctx['ftiq_longitude']
        self.write(vals)

    def action_submit(self):
        self.ensure_one()
        if self.state not in ('draft', 'in_progress', 'returned'):
            raise UserError(_('Cannot submit from current state.'))
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.ensure_one()
        if self.state != 'submitted':
            raise UserError(_('Only submitted visits can be approved.'))
        self.write({'state': 'approved'})

    def action_return(self):
        self.ensure_one()
        if self.state != 'submitted':
            raise UserError(_('Only submitted visits can be returned.'))
        self.write({'state': 'returned'})

    def action_reset_draft(self):
        self.ensure_one()
        if self.state not in ('returned',):
            raise UserError(_('Can only reset returned visits to draft.'))
        self.write({'state': 'draft'})

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
        payment = self.env['account.payment'].create({
            'partner_id': self.partner_id.id,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'is_field_collection': True,
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
        check = self.env['ftiq.stock.check'].create({
            'partner_id': self.partner_id.id,
            'user_id': self.user_id.id,
            'visit_id': self.id,
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
