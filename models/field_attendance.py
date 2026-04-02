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
    entry_reference = fields.Reference(
        selection=[
            ('ftiq.visit', 'Visit'),
            ('ftiq.daily.task', 'Task'),
            ('sale.order', 'Field Order'),
            ('account.payment', 'Collection'),
            ('ftiq.stock.check', 'Stock Check'),
        ],
        string='Started From',
        readonly=True,
        copy=False,
    )

    check_in_time = fields.Datetime(readonly=True)
    check_in_latitude = fields.Float(digits=(10, 7), readonly=True)
    check_in_longitude = fields.Float(digits=(10, 7), readonly=True)
    check_in_address = fields.Char(readonly=True)
    check_in_accuracy = fields.Float(string='Check-in Accuracy (m)', readonly=True)
    check_in_is_mock = fields.Boolean(string='Suspicious Check-in GPS', readonly=True)

    check_out_time = fields.Datetime(readonly=True)
    check_out_latitude = fields.Float(digits=(10, 7), readonly=True)
    check_out_longitude = fields.Float(digits=(10, 7), readonly=True)
    check_out_address = fields.Char(readonly=True)
    check_out_accuracy = fields.Float(string='Check-out Accuracy (m)', readonly=True)
    check_out_is_mock = fields.Boolean(string='Suspicious Check-out GPS', readonly=True)

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
        raise UserError(_('Attendance check-in starts automatically from a visit, field order, collection, or stock check.'))

    def action_check_out(self):
        self.ensure_one()
        if self.state != 'checked_in':
            raise UserError(_('You must check in first.'))
        ctx = self.env.context
        lat = ctx.get('ftiq_latitude', 0)
        lng = ctx.get('ftiq_longitude', 0)
        if not lat or not lng:
            raise UserError(_('GPS location is required for check-out. Please enable location services and try again.'))
        accuracy = ctx.get('ftiq_accuracy', 0)
        is_mock = ctx.get('ftiq_is_mock', False)
        if is_mock:
            raise UserError(_('Mock location detected. Fake GPS applications are not allowed.'))
        vals = {
            'state': 'checked_out',
            'check_out_time': fields.Datetime.now(),
            'check_out_latitude': lat,
            'check_out_longitude': lng,
            'check_out_accuracy': accuracy,
            'check_out_is_mock': is_mock,
        }
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

    def action_open_entry_document(self):
        self.ensure_one()
        if not self.entry_reference:
            raise UserError(_('No operational document is linked to this attendance record.'))
        return {
            'type': 'ir.actions.act_window',
            'name': self.entry_reference.display_name,
            'res_model': self.entry_reference._name,
            'res_id': self.entry_reference.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def get_active_attendance(self, user_id, attendance_date=None):
        if not user_id:
            return self.env['ftiq.field.attendance']
        attendance_date = fields.Date.to_date(attendance_date or fields.Date.context_today(self))
        return self.search([
            ('user_id', '=', user_id),
            ('date', '=', attendance_date),
            ('state', '=', 'checked_in'),
        ], order='check_in_time desc, id desc', limit=1)

    @api.model
    def ensure_operation_attendance(
        self,
        user_id,
        attendance_date=None,
        latitude=None,
        longitude=None,
        accuracy=0,
        is_mock=False,
        entry_reference=None,
    ):
        attendance_date = fields.Date.to_date(attendance_date or fields.Date.context_today(self))
        attendance = self.get_active_attendance(user_id, attendance_date)
        if attendance:
            return attendance
        if not latitude or not longitude:
            raise UserError(_('Location is required to start field activity. Enable location services and try again.'))
        if is_mock:
            raise UserError(_('Mock location detected. Fake GPS applications are not allowed.'))
        return self.create({
            'user_id': user_id,
            'date': attendance_date,
            'state': 'checked_in',
            'check_in_time': fields.Datetime.now(),
            'check_in_latitude': latitude,
            'check_in_longitude': longitude,
            'check_in_accuracy': accuracy,
            'check_in_is_mock': is_mock,
            'entry_reference': entry_reference,
        })
