from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ftiq_use_state_journal_restriction = fields.Boolean(
        string='Restrict Journals by Partner State',
        related='company_id.ftiq_use_state_journal_restriction',
        readonly=False,
    )
