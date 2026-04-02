from odoo import _, api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_field_invoice = fields.Boolean(compute='_compute_ftiq_document_flags', store=True)
    is_field_payment_move = fields.Boolean(compute='_compute_ftiq_document_flags', store=True)
    ftiq_visit_id = fields.Many2one('ftiq.visit', string='Related Visit', copy=False)
    ftiq_attendance_id = fields.Many2one('ftiq.field.attendance', string='Attendance', copy=False)
    ftiq_daily_task_id = fields.Many2one('ftiq.daily.task', string='Daily Task', copy=False)
    ftiq_user_id = fields.Many2one('res.users', string='Representative', copy=False)
    ftiq_access_user_id = fields.Many2one('res.users', string='Access User', compute='_compute_ftiq_access_scope', store=True, readonly=True)
    ftiq_team_id = fields.Many2one('crm.team', string='Field Team', compute='_compute_ftiq_team_id', store=True, readonly=True)
    ftiq_partner_area_id = fields.Many2one(related='partner_id.ftiq_area_id', store=True)
    ftiq_field_notes = fields.Text(string='Field Notes')

    @api.depends('move_type', 'ftiq_visit_id', 'ftiq_daily_task_id', 'ftiq_attendance_id', 'origin_payment_id.is_field_collection')
    def _compute_ftiq_document_flags(self):
        for rec in self:
            rec.is_field_invoice = bool(
                rec.move_type == 'out_invoice'
                and (rec.ftiq_visit_id or rec.ftiq_daily_task_id or rec.ftiq_attendance_id)
            )
            rec.is_field_payment_move = bool(rec.origin_payment_id and rec.origin_payment_id.is_field_collection)

    @api.depends('origin_payment_id.ftiq_user_id', 'ftiq_user_id', 'invoice_user_id')
    def _compute_ftiq_access_scope(self):
        for rec in self:
            rec.ftiq_access_user_id = rec.origin_payment_id.ftiq_user_id or rec.ftiq_user_id or rec.invoice_user_id

    @api.depends('origin_payment_id.ftiq_team_id', 'ftiq_access_user_id.sale_team_id')
    def _compute_ftiq_team_id(self):
        for rec in self:
            rec.ftiq_team_id = rec.origin_payment_id.ftiq_team_id or rec.ftiq_access_user_id.sale_team_id

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_ftiq_source_fields()
        return records

    def write(self, vals):
        old_state = {record.id: record.state for record in self}
        old_payment_state = {
            record.id: record.payment_state
            for record in self
        }
        result = super().write(vals)
        if any(key in vals for key in (
            'ftiq_visit_id',
            'ftiq_attendance_id',
            'ftiq_daily_task_id',
            'invoice_user_id',
            'partner_id',
            'origin_payment_id',
        )):
            self._sync_ftiq_source_fields()
        if 'state' in vals or 'payment_state' in vals:
            self._notify_mobile_state_change(
                old_state=old_state,
                old_payment_state=old_payment_state,
            )
        return result

    def _sync_ftiq_source_fields(self):
        for rec in self:
            vals = {}
            if rec.origin_payment_id and rec.origin_payment_id.is_field_collection:
                payment = rec.origin_payment_id
                if payment.ftiq_visit_id and rec.ftiq_visit_id != payment.ftiq_visit_id:
                    vals['ftiq_visit_id'] = payment.ftiq_visit_id.id
                if payment.ftiq_daily_task_id and rec.ftiq_daily_task_id != payment.ftiq_daily_task_id:
                    vals['ftiq_daily_task_id'] = payment.ftiq_daily_task_id.id
                if payment.ftiq_attendance_id and rec.ftiq_attendance_id != payment.ftiq_attendance_id:
                    vals['ftiq_attendance_id'] = payment.ftiq_attendance_id.id
                if payment.ftiq_user_id and rec.ftiq_user_id != payment.ftiq_user_id:
                    vals['ftiq_user_id'] = payment.ftiq_user_id.id
            elif rec.move_type == 'out_invoice':
                source_task = rec.ftiq_daily_task_id
                source_visit = rec.ftiq_visit_id or source_task.visit_id
                source_attendance = (
                    rec.ftiq_attendance_id
                    or source_visit.attendance_id
                    or source_task.visit_id.attendance_id
                    or source_task._find_attendance_for(source_task.user_id.id)
                )
                source_user = rec.ftiq_user_id or source_task.user_id or source_visit.user_id or rec.invoice_user_id
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

    def _invoice_notification_users(self):
        self.ensure_one()
        notification_model = self.env['ftiq.mobile.notification']
        users = (self.ftiq_user_id | notification_model.approval_users_for(self)).filtered(
            lambda user: not user.share and user.active
        )
        return (users - self.env.user).filtered(
            lambda user: user.company_id == self.company_id
        )

    def _notify_mobile_state_change(self, old_state=None, old_payment_state=None):
        state_labels = dict(self._fields['state'].selection)
        payment_labels = dict(self._fields['payment_state'].selection)
        for record in self.filtered(lambda move: move.move_type == 'out_invoice'):
            previous_state = (old_state or {}).get(record.id)
            previous_payment_state = (old_payment_state or {}).get(record.id)
            recipients = record._invoice_notification_users()
            if not recipients:
                continue
            subject = ''
            body = ''
            if previous_state != record.state:
                subject = _('Invoice updated')
                body = _(
                    'Invoice %s state is now %s.'
                ) % (
                    record.display_name,
                    state_labels.get(record.state, record.state or ''),
                )
            elif previous_payment_state != record.payment_state:
                subject = _('Invoice payment updated')
                body = _(
                    'Invoice %s payment status is now %s.'
                ) % (
                    record.display_name,
                    payment_labels.get(record.payment_state, record.payment_state or ''),
                )
            if not subject or not body:
                continue
            record.message_post(
                subject=subject,
                body=body,
                partner_ids=recipients.mapped('partner_id').ids,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
