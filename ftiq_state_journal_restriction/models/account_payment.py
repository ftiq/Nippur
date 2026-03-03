from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    ftiq_allowed_journal_ids = fields.Many2many(
        comodel_name='account.journal',
        compute='_compute_ftiq_allowed_journal_ids',
    )

    @api.depends('payment_type', 'partner_id', 'partner_id.state_id', 'company_id')
    def _compute_ftiq_allowed_journal_ids(self):
        for pay in self:
            company = pay.company_id or pay.env.company
            if not company.ftiq_use_state_journal_restriction:
                pay.ftiq_allowed_journal_ids = pay.available_journal_ids
                continue
            state = pay.partner_id.state_id
            if not state:
                pay.ftiq_allowed_journal_ids = pay.env['account.journal']
                continue
            state_journals = state.ftiq_journal_ids
            if not state_journals:
                pay.ftiq_allowed_journal_ids = pay.env['account.journal']
                continue
            pay.ftiq_allowed_journal_ids = pay.available_journal_ids & state_journals

    def _ftiq_get_restricted_available_journals(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        if not company.ftiq_use_state_journal_restriction:
            return self.env['account.journal']
        state = self.partner_id.state_id
        if not state or not state.ftiq_journal_ids:
            return self.env['account.journal']
        return self.available_journal_ids & state.ftiq_journal_ids

    @api.depends('payment_type', 'partner_id', 'partner_id.state_id', 'company_id')
    def _compute_available_journal_ids(self):
        super()._compute_available_journal_ids()
        for pay in self:
            company = pay.company_id or self.env.company
            if not company.ftiq_use_state_journal_restriction:
                continue
            state = pay.partner_id.state_id
            if not state:
                continue
            journals = state.ftiq_journal_ids
            if not journals:
                continue
            restricted = pay.available_journal_ids & journals
            pay.available_journal_ids = restricted

    @api.depends('company_id', 'partner_id', 'partner_id.state_id', 'payment_type')
    def _compute_journal_id(self):
        super()._compute_journal_id()
        for pay in self:
            company = pay.company_id or self.env.company
            state = pay.partner_id.state_id
            if not company.ftiq_use_state_journal_restriction or not state or not state.ftiq_journal_ids:
                continue
            restricted = pay._ftiq_get_restricted_available_journals()
            if not restricted:
                continue
            if pay.journal_id and pay.journal_id in restricted:
                continue
            pay.journal_id = restricted[:1]

    @api.constrains('journal_id', 'partner_id', 'company_id')
    def _check_ftiq_state_journal(self):
        for pay in self:
            company = pay.company_id or self.env.company
            state = pay.partner_id.state_id
            if not company.ftiq_use_state_journal_restriction or not state or not state.ftiq_journal_ids:
                continue
            restricted = pay._ftiq_get_restricted_available_journals()
            if pay.journal_id and restricted and pay.journal_id not in restricted:
                raise ValidationError(_('The selected journal is not allowed for this partner state.'))
