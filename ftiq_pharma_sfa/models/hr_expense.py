from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    is_field_expense = fields.Boolean(string='Field Expense', default=False)
    ftiq_attendance_id = fields.Many2one('ftiq.field.attendance', string='Attendance', copy=False)
    ftiq_visit_id = fields.Many2one('ftiq.visit', string='Related Visit', copy=False)
    ftiq_daily_task_id = fields.Many2one('ftiq.daily.task', string='Daily Task', copy=False)
    ftiq_partner_id = fields.Many2one('res.partner', string='Client', copy=False)
    ftiq_user_id = fields.Many2one('res.users', string='Representative', copy=False)
    ftiq_team_id = fields.Many2one('crm.team', string='Sales Team', copy=False)
    ftiq_latitude = fields.Float(string='Latitude', digits=(10, 7))
    ftiq_longitude = fields.Float(string='Longitude', digits=(10, 7))
    ftiq_expense_type = fields.Selection([
        ('transport', 'Transportation'),
        ('fuel', 'Fuel'),
        ('food', 'Food & Meals'),
        ('accommodation', 'Accommodation'),
        ('phone', 'Phone & Communication'),
        ('parking', 'Parking'),
        ('other', 'Other'),
    ], string='Field Expense Type')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered('is_field_expense')._sync_ftiq_source_fields()
        return records

    def write(self, vals):
        result = super().write(vals)
        if any(key in vals for key in (
            'is_field_expense', 'ftiq_attendance_id', 'ftiq_visit_id', 'ftiq_daily_task_id',
            'ftiq_partner_id', 'employee_id', 'date',
        )):
            self.filtered('is_field_expense')._sync_ftiq_source_fields()
        return result

    @api.constrains('is_field_expense', 'ftiq_attendance_id', 'ftiq_visit_id', 'ftiq_daily_task_id')
    def _check_ftiq_source_traceability(self):
        for rec in self.filtered('is_field_expense'):
            if not any((rec.ftiq_attendance_id, rec.ftiq_visit_id, rec.ftiq_daily_task_id)):
                raise ValidationError(
                    _('Field expense must be linked to a daily task, a visit, or a valid attendance day.')
                )

    def _sync_ftiq_source_fields(self):
        attendance_model = self.env['ftiq.field.attendance']
        for rec in self.filtered('is_field_expense'):
            source_task = rec.ftiq_daily_task_id
            source_visit = rec.ftiq_visit_id or source_task.visit_id
            source_partner = rec.ftiq_partner_id or source_task.partner_id or source_visit.partner_id
            source_user = rec.ftiq_user_id or source_task.user_id or source_visit.user_id or rec.employee_id.user_id
            source_team = source_task.team_id or source_visit.team_id or source_user.sale_team_id
            source_attendance = rec.ftiq_attendance_id or source_visit.attendance_id
            if not source_attendance and source_user and rec.date:
                source_attendance = attendance_model.get_active_attendance(source_user.id, rec.date)
            vals = {}
            if source_visit and rec.ftiq_visit_id != source_visit:
                vals['ftiq_visit_id'] = source_visit.id
            if source_task and rec.ftiq_daily_task_id != source_task:
                vals['ftiq_daily_task_id'] = source_task.id
            if source_partner and rec.ftiq_partner_id != source_partner:
                vals['ftiq_partner_id'] = source_partner.id
            if source_user and rec.ftiq_user_id != source_user:
                vals['ftiq_user_id'] = source_user.id
            if source_team and rec.ftiq_team_id != source_team:
                vals['ftiq_team_id'] = source_team.id
            if source_attendance and rec.ftiq_attendance_id != source_attendance:
                vals['ftiq_attendance_id'] = source_attendance.id
            if source_visit and source_visit.start_latitude and not rec.ftiq_latitude:
                vals['ftiq_latitude'] = source_visit.start_latitude
            if source_visit and source_visit.start_longitude and not rec.ftiq_longitude:
                vals['ftiq_longitude'] = source_visit.start_longitude
            if vals:
                super(HrExpense, rec).write(vals)
