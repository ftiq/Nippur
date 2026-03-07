from odoo import models, fields, api, _


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_field_collection = fields.Boolean(string='Field Collection', default=False, tracking=True)
    ftiq_visit_id = fields.Many2one('ftiq.visit', string='Related Visit', copy=False)
    ftiq_attendance_id = fields.Many2one('ftiq.field.attendance', string='Attendance', copy=False)
    ftiq_latitude = fields.Float(string='Latitude', digits=(10, 7))
    ftiq_longitude = fields.Float(string='Longitude', digits=(10, 7))
    ftiq_check_number = fields.Char(string='Check Number')
    ftiq_check_date = fields.Date(string='Check Date')
    ftiq_bank_name = fields.Char(string='Bank Name')
    ftiq_receipt_image = fields.Binary(string='Receipt Image', attachment=True)
    ftiq_receipt_image_name = fields.Char(string='Receipt Image Name')
    ftiq_collection_state = fields.Selection([
        ('draft', 'Draft'),
        ('collected', 'Collected'),
        ('deposited', 'Deposited'),
        ('verified', 'Verified'),
    ], string='Collection Status', default='draft', tracking=True)

    def action_ftiq_collect(self):
        self.write({'ftiq_collection_state': 'collected'})

    def action_ftiq_deposit(self):
        self.write({'ftiq_collection_state': 'deposited'})

    def action_ftiq_verify(self):
        self.write({'ftiq_collection_state': 'verified'})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_field_collection') and not vals.get('ftiq_attendance_id'):
                att = self.env['ftiq.field.attendance'].search([
                    ('user_id', '=', self.env.uid),
                    ('date', '=', fields.Date.context_today(self)),
                    ('state', '=', 'checked_in'),
                ], limit=1)
                if att:
                    vals['ftiq_attendance_id'] = att.id
        return super().create(vals_list)
