from odoo import models, fields, api, _
from odoo.exceptions import UserError


class FtiqFieldAttendance(models.Model):
    _name = 'ftiq.field.attendance'
    _description = 'Field Attendance'
    _inherit = ['mail.thread']
    _order = 'check_in_time desc'

    name = fields.Char(readonly=True, default='New', copy=False)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.uid, required=True, tracking=True)
    date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)

    check_in_time = fields.Datetime(readonly=True)
    check_in_latitude = fields.Float(digits=(10, 7), readonly=True)
    check_in_longitude = fields.Float(digits=(10, 7), readonly=True)
    check_in_address = fields.Char(readonly=True)

    check_out_time = fields.Datetime(readonly=True)
    check_out_latitude = fields.Float(digits=(10, 7), readonly=True)
    check_out_longitude = fields.Float(digits=(10, 7), readonly=True)
    check_out_address = fields.Char(readonly=True)

    working_hours = fields.Float(compute='_compute_working_hours', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out'),
    ], default='draft', tracking=True)

    visit_ids = fields.One2many('ftiq.visit', 'attendance_id')
    visit_count = fields.Integer(compute='_compute_visit_count')

    @api.depends('check_in_time', 'check_out_time')
    def _compute_working_hours(self):
        for rec in self:
            if rec.check_in_time and rec.check_out_time:
                delta = rec.check_out_time - rec.check_in_time
                rec.working_hours = delta.total_seconds() / 3600.0
            else:
                rec.working_hours = 0.0

    @api.depends('visit_ids')
    def _compute_visit_count(self):
        for rec in self:
            rec.visit_count = len(rec.visit_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('ftiq.field.attendance') or 'New'
        return super().create(vals_list)

    def action_check_in(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Already checked in.'))
        existing = self.search([
            ('user_id', '=', self.user_id.id),
            ('date', '=', self.date),
            ('state', 'in', ['checked_in']),
            ('id', '!=', self.id),
        ], limit=1)
        if existing:
            raise UserError(_('An open attendance session already exists for today.'))
        vals = {
            'state': 'checked_in',
            'check_in_time': fields.Datetime.now(),
        }
        ctx = self.env.context
        if ctx.get('ftiq_latitude'):
            vals['check_in_latitude'] = ctx['ftiq_latitude']
        if ctx.get('ftiq_longitude'):
            vals['check_in_longitude'] = ctx['ftiq_longitude']
        self.write(vals)

    def action_check_out(self):
        self.ensure_one()
        if self.state != 'checked_in':
            raise UserError(_('You must check in first.'))
        vals = {
            'state': 'checked_out',
            'check_out_time': fields.Datetime.now(),
        }
        ctx = self.env.context
        if ctx.get('ftiq_latitude'):
            vals['check_out_latitude'] = ctx['ftiq_latitude']
        if ctx.get('ftiq_longitude'):
            vals['check_out_longitude'] = ctx['ftiq_longitude']
        self.write(vals)

    def action_open_visits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Visits'),
            'res_model': 'ftiq.visit',
            'view_mode': 'list,form',
            'domain': [('attendance_id', '=', self.id)],
            'context': {'default_attendance_id': self.id, 'default_user_id': self.user_id.id},
        }
