from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    ftiq_use_state_journal_restriction = fields.Boolean(string='Restrict Journals by Partner State')
