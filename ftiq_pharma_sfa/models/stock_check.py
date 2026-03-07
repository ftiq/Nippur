from odoo import models, fields, api, _


class FtiqStockCheck(models.Model):
    _name = 'ftiq.stock.check'
    _description = 'Stock Check at Client'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'check_date desc, id desc'

    name = fields.Char(string='Reference', readonly=True, copy=False, default='New')
    partner_id = fields.Many2one('res.partner', string='Client', required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Representative', default=lambda self: self.env.uid, tracking=True)
    check_date = fields.Datetime(string='Check Date', default=fields.Datetime.now, required=True, tracking=True)
    visit_id = fields.Many2one('ftiq.visit', string='Related Visit')
    attendance_id = fields.Many2one('ftiq.field.attendance', string='Attendance')
    line_ids = fields.One2many('ftiq.stock.check.line', 'check_id', string='Stock Lines')
    total_items = fields.Integer(string='Total Items', compute='_compute_totals', store=True)
    total_qty = fields.Float(string='Total Stock Qty', compute='_compute_totals', store=True)
    notes = fields.Text(string='Notes')
    photo = fields.Binary(string='Shelf Photo', attachment=True)
    photo_name = fields.Char(string='Photo Name')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('reviewed', 'Reviewed'),
    ], string='Status', default='draft', tracking=True)
    latitude = fields.Float(string='Latitude', digits=(10, 7))
    longitude = fields.Float(string='Longitude', digits=(10, 7))

    @api.depends('line_ids.stock_qty')
    def _compute_totals(self):
        for rec in self:
            rec.total_items = len(rec.line_ids)
            rec.total_qty = sum(rec.line_ids.mapped('stock_qty'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('ftiq.stock.check') or 'New'
        return super().create(vals_list)

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.update({
            'name': 'New',
            'state': 'draft',
            'line_ids': [(5, 0, 0)],
            'visit_id': False,
            'attendance_id': False,
            'check_date': fields.Datetime.now(),
        })
        new_check = super().copy(default)
        for line in self.line_ids.sorted(key=lambda l: (l.sequence, l.id)):
            self.env['ftiq.stock.check.line'].create({
                'check_id': new_check.id,
                'sequence': line.sequence,
                'product_id': line.product_id.id,
                'stock_qty': line.stock_qty,
                'expiry_date': line.expiry_date,
                'batch_number': line.batch_number,
                'shelf_position': line.shelf_position,
                'competitor_product': line.competitor_product,
                'competitor_qty': line.competitor_qty,
                'note': line.note,
            })
        return new_check

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_review(self):
        self.write({'state': 'reviewed'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class FtiqStockCheckLine(models.Model):
    _name = 'ftiq.stock.check.line'
    _description = 'Stock Check Line'
    _order = 'sequence, id'

    check_id = fields.Many2one('ftiq.stock.check', string='Stock Check', ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    stock_qty = fields.Float(string='Stock Quantity', required=True)
    expiry_date = fields.Date(string='Expiry Date')
    batch_number = fields.Char(string='Batch Number')
    shelf_position = fields.Char(string='Shelf Position')
    competitor_product = fields.Char(string='Competitor Product')
    competitor_qty = fields.Float(string='Competitor Qty')
    note = fields.Char(string='Note')
