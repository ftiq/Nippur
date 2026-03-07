from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


FTIQ_TARGET_PAYMENT_STATES = ('in_process', 'paid')


class FtiqSalesTarget(models.Model):
    _name = 'ftiq.sales.target'
    _description = 'Sales Target'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    name = fields.Char(string='Name', required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Representative', required=True, tracking=True)
    team_id = fields.Many2one('crm.team', string='Sales Team', compute='_compute_team_id', store=True, readonly=True)
    supervisor_id = fields.Many2one('res.users', string='Supervisor', related='team_id.user_id', store=True)
    date_from = fields.Date(string='Period Start', required=True, tracking=True)
    date_to = fields.Date(string='Period End', required=True, tracking=True)
    target_type = fields.Selection([
        ('visits', 'Visits Count'),
        ('orders', 'Orders Amount'),
        ('collections', 'Collections Amount'),
        ('new_clients', 'New Clients'),
        ('products', 'Product Coverage'),
    ], string='Target Type', required=True, tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    target_value = fields.Float(string='Target Value', required=True, tracking=True)
    achieved_value = fields.Float(string='Achieved Value', compute='_compute_progress')
    achievement_rate = fields.Float(string='Achievement %', compute='_compute_progress')
    line_ids = fields.One2many('ftiq.sales.target.line', 'target_id', string='Product Targets')
    notes = fields.Text(string='Notes')
    linked_visit_count = fields.Integer(compute='_compute_linked_counts')
    linked_order_count = fields.Integer(compute='_compute_linked_counts')
    linked_order_amount = fields.Float(compute='_compute_linked_counts')
    linked_payment_count = fields.Integer(compute='_compute_linked_counts')
    linked_payment_amount = fields.Float(compute='_compute_linked_counts')
    linked_client_count = fields.Integer(compute='_compute_linked_counts')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', tracking=True)

    @api.depends('user_id.sale_team_id')
    def _compute_team_id(self):
        for rec in self:
            rec.team_id = rec.user_id.sale_team_id

    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_('Target end date cannot be earlier than the start date.'))

    @api.depends(
        'target_type',
        'target_value',
        'user_id',
        'date_from',
        'date_to',
        'state',
        'line_ids.target_qty',
        'line_ids.target_amount',
        'line_ids.product_id',
    )
    def _compute_progress(self):
        for rec in self:
            achieved = 0.0
            if rec.state != 'draft' and rec.user_id and rec.date_from and rec.date_to:
                if rec.target_type == 'visits':
                    achieved = self.env['ftiq.visit'].search_count(rec._visit_domain())
                elif rec.target_type == 'orders':
                    orders = self.env['sale.order'].search(rec._order_domain())
                    achieved = sum(orders.mapped('amount_total'))
                elif rec.target_type == 'collections':
                    payments = self.env['account.payment'].search(rec._collection_domain())
                    achieved = sum(payments.mapped('amount'))
                elif rec.target_type == 'new_clients':
                    achieved = self.env['res.partner'].search_count(rec._new_client_domain())
                elif rec.target_type == 'products':
                    if any(line.target_amount for line in rec.line_ids):
                        achieved = sum(rec.line_ids.mapped('achieved_amount'))
                    else:
                        achieved = sum(rec.line_ids.mapped('achieved_qty'))
            rec.achieved_value = achieved
            rec.achievement_rate = (achieved / rec.target_value * 100.0) if rec.target_value else 0.0

    @api.depends(
        'user_id',
        'date_from',
        'date_to',
        'target_type',
        'line_ids.target_qty',
        'line_ids.target_amount',
        'line_ids.product_id',
    )
    def _compute_linked_counts(self):
        for rec in self:
            rec.linked_visit_count = 0
            rec.linked_order_count = 0
            rec.linked_order_amount = 0.0
            rec.linked_payment_count = 0
            rec.linked_payment_amount = 0.0
            rec.linked_client_count = 0
            if not rec.user_id or not rec.date_from or not rec.date_to:
                continue
            rec.linked_visit_count = self.env['ftiq.visit'].search_count(rec._visit_domain())
            orders = self.env['sale.order'].search(rec._order_domain())
            rec.linked_order_count = len(orders)
            rec.linked_order_amount = sum(orders.mapped('amount_total'))
            payments = self.env['account.payment'].search(rec._collection_domain())
            rec.linked_payment_count = len(payments)
            rec.linked_payment_amount = sum(payments.mapped('amount'))
            rec.linked_client_count = self.env['res.partner'].search_count(rec._new_client_domain())

    def _visit_domain(self):
        self.ensure_one()
        return [
            ('user_id', '=', self.user_id.id),
            ('visit_date', '>=', self.date_from),
            ('visit_date', '<=', self.date_to),
            ('state', '=', 'approved'),
        ]

    def _order_domain(self):
        self.ensure_one()
        date_from_dt = fields.Datetime.to_datetime(self.date_from)
        date_to_dt = fields.Datetime.to_datetime(self.date_to) + timedelta(days=1)
        return [
            ('user_id', '=', self.user_id.id),
            ('is_field_order', '=', True),
            ('date_order', '>=', date_from_dt),
            ('date_order', '<', date_to_dt),
            ('state', 'in', ('sale', 'done')),
        ]

    def _collection_domain(self):
        self.ensure_one()
        return [
            ('is_field_collection', '=', True),
            ('ftiq_user_id', '=', self.user_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', 'in', FTIQ_TARGET_PAYMENT_STATES),
        ]

    def _new_client_domain(self):
        self.ensure_one()
        date_from_dt = fields.Datetime.to_datetime(self.date_from)
        date_to_dt = fields.Datetime.to_datetime(self.date_to) + timedelta(days=1)
        return [
            '|',
            ('user_id', '=', self.user_id.id),
            '&',
            ('user_id', '=', False),
            ('create_uid', '=', self.user_id.id),
            ('create_date', '>=', date_from_dt),
            ('create_date', '<', date_to_dt),
            '|', '|',
            ('is_ftiq_doctor', '=', True),
            ('is_ftiq_center', '=', True),
            ('is_ftiq_pharmacy', '=', True),
        ]

    def action_view_linked_visits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Approved Visits'),
            'res_model': 'ftiq.visit',
            'view_mode': 'list,form',
            'domain': self._visit_domain(),
        }

    def action_view_linked_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Field Orders'),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': self._order_domain(),
        }

    def action_view_linked_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Collections'),
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': self._collection_domain(),
        }

    def action_view_linked_clients(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Clients'),
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': self._new_client_domain(),
        }

    def action_activate(self):
        self.write({'state': 'active'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.setdefault('name', _('%s (Copy)') % self.name)
        default.update({
            'state': 'draft',
            'line_ids': [(5, 0, 0)],
        })
        new_target = super().copy(default)
        for line in self.line_ids:
            self.env['ftiq.sales.target.line'].create({
                'target_id': new_target.id,
                'product_id': line.product_id.id,
                'target_qty': line.target_qty,
                'target_amount': line.target_amount,
            })
        return new_target


class FtiqSalesTargetLine(models.Model):
    _name = 'ftiq.sales.target.line'
    _description = 'Sales Target Line'

    target_id = fields.Many2one('ftiq.sales.target', string='Target', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    target_qty = fields.Float(string='Target Qty')
    target_amount = fields.Float(string='Target Amount')
    achieved_qty = fields.Float(string='Achieved Qty', compute='_compute_progress')
    achieved_amount = fields.Float(string='Achieved Amount', compute='_compute_progress')
    achievement_rate = fields.Float(string='Achievement %', compute='_compute_rate')

    @api.depends(
        'target_id.user_id',
        'target_id.date_from',
        'target_id.date_to',
        'target_id.state',
        'product_id',
    )
    def _compute_progress(self):
        for line in self:
            line.achieved_qty = 0.0
            line.achieved_amount = 0.0
            target = line.target_id
            if not target or not target.user_id or not target.date_from or not target.date_to or not line.product_id:
                continue
            orders = self.env['sale.order'].search(target._order_domain())
            order_lines = orders.mapped('order_line').filtered(lambda order_line: order_line.product_id == line.product_id)
            line.achieved_qty = sum(order_lines.mapped('product_uom_qty'))
            line.achieved_amount = sum(order_lines.mapped('price_subtotal'))

    @api.depends('target_qty', 'achieved_qty', 'target_amount', 'achieved_amount')
    def _compute_rate(self):
        for line in self:
            if line.target_qty:
                line.achievement_rate = (line.achieved_qty / line.target_qty * 100.0)
            elif line.target_amount:
                line.achievement_rate = (line.achieved_amount / line.target_amount * 100.0)
            else:
                line.achievement_rate = 0.0
