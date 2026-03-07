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
            if vals.get('is_field_order') and not vals.get('ftiq_attendance_id'):
                rep_id = vals.get('user_id') or self.env.uid
                att = self.env['ftiq.field.attendance'].get_active_attendance(rep_id, fields.Date.context_today(self))
                if att:
                    vals['ftiq_attendance_id'] = att.id
        return super().create(vals_list)

    def action_confirm(self):
        self._ensure_ftiq_operational_attendance()
        result = super().action_confirm()
        completed_tasks = self.filtered(
            lambda order: order.ftiq_daily_task_id and order.ftiq_daily_task_id.state not in ('completed', 'cancelled')
        )
        if completed_tasks:
            completed_tasks.mapped('ftiq_daily_task_id').write({
                'state': 'completed',
                'completed_date': fields.Datetime.now(),
            })
        return result

    def _create_invoices(self, grouped=False, final=False, date=None):
        moves = super()._create_invoices(grouped=grouped, final=final, date=date)
        for move in moves:
            origins = move.line_ids.sale_line_ids.order_id
            field_orders = origins.filtered('ftiq_visit_id')
            if field_orders and not move.ftiq_visit_id:
                move.ftiq_visit_id = field_orders[0].ftiq_visit_id.id
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
