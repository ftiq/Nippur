from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_field_order = fields.Boolean(string='Field Order', default=False, tracking=True)
    ftiq_visit_id = fields.Many2one('ftiq.visit', string='Related Visit', copy=False)
    ftiq_attendance_id = fields.Many2one('ftiq.field.attendance', string='Attendance', copy=False)
    ftiq_latitude = fields.Float(string='Latitude', digits=(10, 7))
    ftiq_longitude = fields.Float(string='Longitude', digits=(10, 7))
    ftiq_daily_task_id = fields.Many2one('ftiq.daily.task', string='Daily Task', copy=False)
    ftiq_priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Urgent'),
        ('2', 'Very Urgent'),
    ], string='Field Priority', default='0')
    ftiq_delivery_notes = fields.Text(string='Field Delivery Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_field_order') and vals.get('ftiq_visit_id') and not vals.get('ftiq_daily_task_id'):
                visit = self.env['ftiq.visit'].browse(vals['ftiq_visit_id'])
                if visit.plan_line_id.daily_task_id:
                    vals['ftiq_daily_task_id'] = visit.plan_line_id.daily_task_id.id
            if vals.get('is_field_order') and not vals.get('ftiq_attendance_id'):
                rep_id = vals.get('user_id') or self.env.uid
                att = self.env['ftiq.field.attendance'].get_active_attendance(rep_id, fields.Date.context_today(self))
                if att:
                    vals['ftiq_attendance_id'] = att.id
        return super().create(vals_list)

    def action_confirm(self):
        self._ensure_ftiq_operational_attendance()
        result = super().action_confirm()
        completed_tasks = self.filtered('ftiq_daily_task_id').mapped('ftiq_daily_task_id')
        if completed_tasks:
            completed_tasks._mark_linked_execution_confirmed(fields.Datetime.now())
        self._notify_mobile_order_confirmed()
        return result

    def _create_invoices(self, grouped=False, final=False, date=None):
        moves = super()._create_invoices(grouped=grouped, final=final, date=date)
        for move in moves:
            origins = move.line_ids.sale_line_ids.order_id
            field_orders = origins.filtered(lambda order: order.is_field_order or order.ftiq_visit_id or order.ftiq_daily_task_id)
            if field_orders:
                field_order = field_orders[0]
                vals = {}
                if field_order.ftiq_visit_id and not move.ftiq_visit_id:
                    vals['ftiq_visit_id'] = field_order.ftiq_visit_id.id
                if field_order.ftiq_attendance_id and not move.ftiq_attendance_id:
                    vals['ftiq_attendance_id'] = field_order.ftiq_attendance_id.id
                if field_order.ftiq_daily_task_id and not move.ftiq_daily_task_id:
                    vals['ftiq_daily_task_id'] = field_order.ftiq_daily_task_id.id
                if field_order.user_id and not move.ftiq_user_id:
                    vals['ftiq_user_id'] = field_order.user_id.id
                if vals:
                    move.write(vals)
                field_order._notify_mobile_invoice_created(move)
        return moves

    def _ensure_ftiq_operational_attendance(self):
        Attendance = self.env['ftiq.field.attendance']
        ctx = self.env.context
        latitude = ctx.get('ftiq_latitude')
        longitude = ctx.get('ftiq_longitude')
        accuracy = ctx.get('ftiq_accuracy', 0)
        is_mock = ctx.get('ftiq_is_mock', False)
        for order in self.filtered('is_field_order'):
            if latitude and not order.ftiq_latitude:
                order.ftiq_latitude = latitude
            if longitude and not order.ftiq_longitude:
                order.ftiq_longitude = longitude
            if order.ftiq_attendance_id:
                continue
            attendance = Attendance.get_active_attendance(order.user_id.id, fields.Date.context_today(order))
            if not attendance:
                attendance = Attendance.ensure_operation_attendance(
                    order.user_id.id,
                    attendance_date=fields.Date.context_today(order),
                    latitude=order.ftiq_latitude or latitude,
                    longitude=order.ftiq_longitude or longitude,
                    accuracy=accuracy,
                    is_mock=is_mock,
                    entry_reference=f'{order._name},{order.id}',
                )
            order.ftiq_attendance_id = attendance.id

    def _notify_mobile_order_confirmed(self):
        notification_model = self.env['ftiq.mobile.notification']
        for order in self.filtered('is_field_order'):
            recipients = (notification_model.approval_users_for(order) | order.user_id) - self.env.user
            notification_model.create_for_users(
                recipients,
                title=_('Order confirmed'),
                body=_('Order %s was confirmed.') % order.name,
                category='order',
                priority='normal',
                target=order,
                source=order,
                author=self.env.user,
                payload={
                    'order_id': order.id,
                    'event': 'confirmed',
                },
                event_key=f'order:{order.id}:confirmed',
            )

    def _notify_mobile_invoice_created(self, move):
        self.ensure_one()
        notification_model = self.env['ftiq.mobile.notification']
        recipients = (notification_model.approval_users_for(self) | self.user_id) - self.env.user
        notification_model.create_for_users(
            recipients,
            title=_('Invoice created'),
            body=_('Invoice %s was created from order %s.') % (move.display_name, self.name),
            category='invoice',
            priority='normal',
            target=move,
            source=self,
            author=self.env.user,
            payload={
                'invoice_id': move.id,
                'order_id': self.id,
                'event': 'created',
            },
            event_key=f'invoice:{move.id}:created',
        )
