from odoo import models, fields, api, _


class FtiqSalesTarget(models.Model):
    _name = 'ftiq.sales.target'
    _description = 'Sales Target'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    name = fields.Char(string='Name', required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Representative', required=True, tracking=True)
    supervisor_id = fields.Many2one('res.users', string='Supervisor', related='user_id.ftiq_supervisor_id', store=True)
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
    achieved_value = fields.Float(string='Achieved Value', compute='_compute_achieved', store=True)
    achievement_rate = fields.Float(string='Achievement %', compute='_compute_achieved', store=True)
    line_ids = fields.One2many('ftiq.sales.target.line', 'target_id', string='Product Targets')
    notes = fields.Text(string='Notes')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', tracking=True)

    @api.depends('target_type', 'target_value', 'user_id', 'date_from', 'date_to', 'state')
    def _compute_achieved(self):
        for rec in self:
            achieved = 0.0
            if rec.state != 'draft' and rec.user_id and rec.date_from and rec.date_to:
                if rec.target_type == 'visits':
                    domain = [
                        ('user_id', '=', rec.user_id.id),
                        ('visit_date', '>=', rec.date_from),
                        ('visit_date', '<=', rec.date_to),
                        ('state', '=', 'approved'),
                    ]
                    achieved = self.env['ftiq.visit'].search_count(domain)
                elif rec.target_type == 'orders':
                    domain = [
                        ('user_id', '=', rec.user_id.id),
                        ('is_field_order', '=', True),
                        ('date_order', '>=', fields.Datetime.to_datetime(rec.date_from)),
                        ('date_order', '<=', fields.Datetime.to_datetime(rec.date_to)),
                        ('state', 'in', ('sale', 'done')),
                    ]
                    orders = self.env['sale.order'].search(domain)
                    achieved = sum(orders.mapped('amount_total'))
                elif rec.target_type == 'collections':
                    domain = [
                        ('is_field_collection', '=', True),
                        ('create_uid', '=', rec.user_id.id),
                        ('date', '>=', rec.date_from),
                        ('date', '<=', rec.date_to),
                        ('state', '=', 'posted'),
                    ]
                    payments = self.env['account.payment'].search(domain)
                    achieved = sum(payments.mapped('amount'))
                elif rec.target_type == 'new_clients':
                    partner_domain = [
                        ('create_uid', '=', rec.user_id.id),
                        ('create_date', '>=', fields.Datetime.to_datetime(rec.date_from)),
                        ('create_date', '<=', fields.Datetime.to_datetime(rec.date_to)),
                        '|', ('is_ftiq_doctor', '=', True),
                        '|', ('is_ftiq_center', '=', True),
                        ('is_ftiq_pharmacy', '=', True),
                    ]
                    achieved = self.env['res.partner'].search_count(partner_domain)
            rec.achieved_value = achieved
            rec.achievement_rate = (achieved / rec.target_value * 100) if rec.target_value else 0.0

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
                'achieved_qty': 0.0,
                'achieved_amount': 0.0,
            })
        return new_target


class FtiqSalesTargetLine(models.Model):
    _name = 'ftiq.sales.target.line'
    _description = 'Sales Target Line'

    target_id = fields.Many2one('ftiq.sales.target', string='Target', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    target_qty = fields.Float(string='Target Qty')
    target_amount = fields.Float(string='Target Amount')
    achieved_qty = fields.Float(string='Achieved Qty')
    achieved_amount = fields.Float(string='Achieved Amount')
    achievement_rate = fields.Float(string='Achievement %', compute='_compute_rate', store=True)

    @api.depends('target_qty', 'achieved_qty', 'target_amount', 'achieved_amount')
    def _compute_rate(self):
        for line in self:
            if line.target_qty:
                line.achievement_rate = (line.achieved_qty / line.target_qty * 100)
            elif line.target_amount:
                line.achievement_rate = (line.achieved_amount / line.target_amount * 100)
            else:
                line.achievement_rate = 0.0
