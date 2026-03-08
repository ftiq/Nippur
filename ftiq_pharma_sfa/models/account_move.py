from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_field_invoice = fields.Boolean(compute='_compute_is_field_invoice', store=True)
    ftiq_visit_id = fields.Many2one('ftiq.visit', string='Related Visit', copy=False)
    ftiq_attendance_id = fields.Many2one('ftiq.field.attendance', string='Attendance', copy=False)
    ftiq_daily_task_id = fields.Many2one('ftiq.daily.task', string='Daily Task', copy=False)
    ftiq_user_id = fields.Many2one('res.users', string='Representative', copy=False)
    ftiq_partner_area_id = fields.Many2one(related='partner_id.ftiq_area_id', store=True)
    ftiq_field_notes = fields.Text(string='Field Notes')

    @api.depends('move_type', 'ftiq_visit_id', 'ftiq_daily_task_id', 'ftiq_attendance_id')
    def _compute_is_field_invoice(self):
        for rec in self:
            rec.is_field_invoice = bool(
                rec.move_type == 'out_invoice'
                and (rec.ftiq_visit_id or rec.ftiq_daily_task_id or rec.ftiq_attendance_id)
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_ftiq_source_fields()
        return records

    def write(self, vals):
        result = super().write(vals)
        if any(key in vals for key in ('ftiq_visit_id', 'ftiq_attendance_id', 'ftiq_daily_task_id', 'invoice_user_id', 'partner_id')):
            self._sync_ftiq_source_fields()
        return result

    def _sync_ftiq_source_fields(self):
        for rec in self.filtered(lambda move: move.move_type == 'out_invoice'):
            source_task = rec.ftiq_daily_task_id
            source_visit = rec.ftiq_visit_id or source_task.visit_id
            source_attendance = (
                rec.ftiq_attendance_id
                or source_visit.attendance_id
                or source_task.visit_id.attendance_id
                or source_task._find_attendance_for(source_task.user_id.id)
            )
            source_user = rec.ftiq_user_id or source_task.user_id or source_visit.user_id or rec.invoice_user_id
            vals = {}
            if source_visit and rec.ftiq_visit_id != source_visit:
                vals['ftiq_visit_id'] = source_visit.id
            if source_task and rec.ftiq_daily_task_id != source_task:
                vals['ftiq_daily_task_id'] = source_task.id
            if source_attendance and rec.ftiq_attendance_id != source_attendance:
                vals['ftiq_attendance_id'] = source_attendance.id
            if source_user and rec.ftiq_user_id != source_user:
                vals['ftiq_user_id'] = source_user.id
            if vals:
                super(AccountMove, rec).write(vals)
