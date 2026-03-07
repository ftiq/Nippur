from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_field_order = fields.Boolean(string='Field Order', default=False, tracking=True)
    ftiq_visit_id = fields.Many2one('ftiq.visit', string='Related Visit', copy=False)
    ftiq_attendance_id = fields.Many2one('ftiq.field.attendance', string='Attendance', copy=False)
    ftiq_latitude = fields.Float(string='Latitude', digits=(10, 7))
    ftiq_longitude = fields.Float(string='Longitude', digits=(10, 7))
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
                att = self.env['ftiq.field.attendance'].search([
                    ('user_id', '=', self.env.uid),
                    ('date', '=', fields.Date.context_today(self)),
                    ('state', '=', 'checked_in'),
                ], limit=1)
                if att:
                    vals['ftiq_attendance_id'] = att.id
        return super().create(vals_list)
