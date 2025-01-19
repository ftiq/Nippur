from odoo import models, fields # type: ignore

class AccountMove(models.Model):
    _inherit = 'account.move'

    representative_id = fields.Many2one(
        'res.users',
        string='Sales Representative',
        help='Sales representative responsible for this invoice.',
    )
