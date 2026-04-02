from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class FtiqStockCheck(models.Model):
    _name = 'ftiq.stock.check'
    _description = 'Stock Check at Client'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'check_date desc, id desc'

    name = fields.Char(string='Reference', readonly=True, copy=False, default='New')
    partner_id = fields.Many2one('res.partner', string='Client', required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Representative', default=lambda self: self.env.uid, tracking=True)
    team_id = fields.Many2one('crm.team', string='Sales Team', compute='_compute_team_id', store=True, readonly=True)
    check_date = fields.Datetime(string='Check Date', default=fields.Datetime.now, required=True, tracking=True)
    visit_id = fields.Many2one('ftiq.visit', string='Related Visit')
    attendance_id = fields.Many2one('ftiq.field.attendance', string='Attendance')
    ftiq_daily_task_id = fields.Many2one('ftiq.daily.task', string='Daily Task', copy=False)
    line_ids = fields.One2many('ftiq.stock.check.line', 'check_id', string='Stock Lines')
    total_items = fields.Integer(string='Total Items', compute='_compute_totals', store=True)
    total_qty = fields.Float(string='Total Stock Qty', compute='_compute_totals', store=True)
    notes = fields.Text(string='Notes')
    photo = fields.Binary(string='Shelf Photo', attachment=True)
    photo_name = fields.Char(string='Photo Name')
    reviewed_by_id = fields.Many2one('res.users', string='Reviewed By', readonly=True)
    reviewed_on = fields.Datetime(string='Reviewed On', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('reviewed', 'Reviewed'),
    ], string='Status', default='draft', tracking=True)
    latitude = fields.Float(string='Latitude', digits=(10, 7))
    longitude = fields.Float(string='Longitude', digits=(10, 7))

    @api.depends('visit_id.team_id', 'ftiq_daily_task_id.team_id', 'user_id.sale_team_id')
    def _compute_team_id(self):
        for rec in self:
            rec.team_id = rec.visit_id.team_id or rec.ftiq_daily_task_id.team_id or rec.user_id.sale_team_id

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
            if not vals.get('attendance_id') and vals.get('user_id'):
                check_date = fields.Datetime.to_datetime(vals.get('check_date')) or fields.Datetime.now()
                attendance = self.env['ftiq.field.attendance'].search([
                    ('user_id', '=', vals['user_id']),
                    ('date', '=', check_date.date()),
                    ('state', '=', 'checked_in'),
                ], limit=1)
                if attendance:
                    vals['attendance_id'] = attendance.id
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
                'competitor_product_id': line.competitor_product_id.id,
                'competitor_product': line.competitor_product,
                'competitor_qty': line.competitor_qty,
                'note': line.note,
            })
        return new_check

    def action_submit(self):
        for rec in self:
            if not (rec.latitude and rec.longitude):
                rec._capture_location_from_context()
            if not rec.attendance_id and rec.user_id:
                rec.attendance_id = self.env['ftiq.field.attendance'].ensure_operation_attendance(
                    rec.user_id.id,
                    attendance_date=fields.Datetime.to_datetime(rec.check_date or fields.Datetime.now()).date(),
                    latitude=rec.latitude or self.env.context.get('ftiq_latitude'),
                    longitude=rec.longitude or self.env.context.get('ftiq_longitude'),
                    accuracy=self.env.context.get('ftiq_accuracy', 0),
                    is_mock=self.env.context.get('ftiq_is_mock', False),
                    entry_reference=f'{rec._name},{rec.id}',
                ).id
            if rec.state != 'draft':
                raise UserError(_('Only draft stock checks can be submitted.'))
            if not rec.line_ids:
                raise UserError(_('Add at least one stock line before submitting the stock check.'))
            if not (rec.latitude and rec.longitude):
                raise UserError(_('GPS coordinates are required before submitting the stock check.'))
        self.write({'state': 'submitted'})
        self.filtered('ftiq_daily_task_id').mapped('ftiq_daily_task_id')._mark_linked_execution_submitted(fields.Datetime.now())
        self._notify_mobile_status_change('submitted')

    def action_review(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Only submitted stock checks can be reviewed.'))
        self.write({
            'state': 'reviewed',
            'reviewed_by_id': self.env.user.id,
            'reviewed_on': fields.Datetime.now(),
        })
        self.filtered('ftiq_daily_task_id').mapped('ftiq_daily_task_id')._mark_linked_execution_confirmed(fields.Datetime.now())
        self._notify_mobile_status_change('reviewed')

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Only submitted stock checks can be reset to draft.'))
        self.write({'state': 'draft'})
        self._notify_mobile_status_change('reset')

    def _capture_location_from_context(self):
        self.ensure_one()
        ctx = self.env.context
        latitude = ctx.get('ftiq_latitude')
        longitude = ctx.get('ftiq_longitude')
        if latitude and longitude:
            self.write({
                'latitude': latitude,
                'longitude': longitude,
            })

    def _notify_mobile_status_change(self, event_key):
        notification_model = self.env['ftiq.mobile.notification']
        for rec in self:
            if event_key == 'submitted':
                recipients = notification_model.approval_users_for(rec) - rec.user_id
                title = _('Stock check submitted')
                body = _('Stock check %s was submitted and is awaiting review.') % rec.display_name
                priority = 'normal'
            elif event_key == 'reviewed':
                recipients = rec.user_id
                title = _('Stock check reviewed')
                body = _('Stock check %s was reviewed.') % rec.display_name
                priority = 'normal'
            else:
                recipients = rec.user_id
                title = _('Stock check reset')
                body = _('Stock check %s was reset to draft.') % rec.display_name
                priority = 'urgent'
            notification_model.create_for_users(
                recipients,
                title=title,
                body=body,
                category='stock_check',
                priority=priority,
                target=rec,
                source=rec,
                author=self.env.user,
                payload={
                    'stock_check_id': rec.id,
                    'event': event_key,
                },
                event_key=f'stock_check:{rec.id}:{event_key}',
            )


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
    competitor_product_id = fields.Many2one('product.product', string='Competitor Product Reference')
    competitor_product = fields.Char(string='Competitor Product')
    competitor_qty = fields.Float(string='Competitor Qty')
    note = fields.Char(string='Note')

    @api.constrains('stock_qty', 'competitor_qty')
    def _check_non_negative_quantities(self):
        for rec in self:
            if rec.stock_qty < 0 or rec.competitor_qty < 0:
                raise ValidationError(_('Stock quantities cannot be negative.'))

    @api.constrains('check_id', 'product_id')
    def _check_unique_product_per_check(self):
        for rec in self:
            if not rec.check_id or not rec.product_id:
                continue
            duplicates = rec.check_id.line_ids.filtered(lambda line: line.product_id == rec.product_id and line != rec)
            if duplicates:
                raise ValidationError(_('Each product can only appear once per stock check.'))
