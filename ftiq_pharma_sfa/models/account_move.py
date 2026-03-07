from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    ftiq_visit_id = fields.Many2one('ftiq.visit', string='Related Visit', copy=False)
    ftiq_field_notes = fields.Text(string='Field Notes')
