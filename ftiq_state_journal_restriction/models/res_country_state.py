from odoo import fields, models


class ResCountryState(models.Model):
    _inherit = 'res.country.state'

    ftiq_journal_ids = fields.Many2many(
        'account.journal',
        'ftiq_state_account_journal_rel',
        'state_id',
        'journal_id',
        string='Journals',
    )
