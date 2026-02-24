from odoo import api, models, Command


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _ftiq_get_partner_state_journals(self):
        company = self.company_id or self.env.company
        if not company.ftiq_use_state_journal_restriction:
            return self.env['account.journal']
        state = self.partner_id.state_id
        if not state:
            return self.env['account.journal']
        return state.ftiq_journal_ids

    @api.depends('payment_type', 'company_id', 'can_edit_wizard', 'partner_id', 'partner_id.state_id')
    def _compute_available_journal_ids(self):
        super()._compute_available_journal_ids()
        for wizard in self:
            journals = wizard._ftiq_get_partner_state_journals()
            if not journals:
                continue
            restricted = wizard.available_journal_ids & journals
            if restricted:
                wizard.available_journal_ids = [Command.set(restricted.ids)]
