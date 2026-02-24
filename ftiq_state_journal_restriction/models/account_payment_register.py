from odoo import api, models, Command, fields, _


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    ftiq_allowed_journal_ids = fields.Many2many(
        comodel_name='account.journal',
        compute='_compute_ftiq_allowed_journal_ids',
    )

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
            company = wizard.company_id or wizard.env.company
            if not company.ftiq_use_state_journal_restriction:
                continue
            state = wizard.partner_id.state_id
            if not state:
                wizard.available_journal_ids = [Command.set([])]
                continue
            state_journals = state.ftiq_journal_ids
            if not state_journals:
                wizard.available_journal_ids = [Command.set([])]
                continue
            restricted = wizard.available_journal_ids & state_journals
            wizard.available_journal_ids = [Command.set(restricted.ids)]

    @api.depends('payment_type', 'company_id', 'can_edit_wizard', 'partner_id', 'partner_id.state_id')
    def _compute_ftiq_allowed_journal_ids(self):
        for wizard in self:
            available_journals = wizard.env['account.journal']
            for batch in wizard.batches:
                available_journals |= wizard._get_batch_available_journals(batch)

            company = wizard.company_id or wizard.env.company
            if not company.ftiq_use_state_journal_restriction:
                wizard.ftiq_allowed_journal_ids = available_journals
                continue
            state = wizard.partner_id.state_id
            if not state:
                wizard.ftiq_allowed_journal_ids = wizard.env['account.journal']
                continue
            state_journals = state.ftiq_journal_ids
            if not state_journals:
                wizard.ftiq_allowed_journal_ids = wizard.env['account.journal']
                continue
            wizard.ftiq_allowed_journal_ids = available_journals & state_journals

    @api.depends('available_journal_ids')
    def _compute_journal_id(self):
        super()._compute_journal_id()
        for wizard in self:
            company = wizard.company_id or wizard.env.company
            state = wizard.partner_id.state_id
            if not company.ftiq_use_state_journal_restriction or not state or not state.ftiq_journal_ids:
                continue
            restricted = wizard.ftiq_allowed_journal_ids
            if restricted and wizard.journal_id not in restricted:
                wizard.journal_id = restricted[:1]
            elif not restricted:
                wizard.journal_id = False

    def action_create_payments(self):
        return super().action_create_payments()
