from odoo import api, models, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

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
            if journals:
                pay.available_journal_ids = pay.available_journal_ids & journals

    @api.depends('company_id', 'partner_id', 'partner_id.state_id', 'payment_type')
    def _compute_journal_id(self):
        super()._compute_journal_id()
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
            if pay.journal_id and pay.journal_id in pay.available_journal_ids:
                continue
            if pay.available_journal_ids:
                pay.journal_id = pay.available_journal_ids[:1]
            else:
                pay.journal_id = False

    @api.constrains('journal_id', 'partner_id', 'company_id')
    def _check_ftiq_state_journal(self):
        for pay in self:
            company = pay.company_id or self.env.company
            if not company.ftiq_use_state_journal_restriction:
                continue
            state = pay.partner_id.state_id
            if not state:
                continue
            journals = state.ftiq_journal_ids
            if journals and pay.journal_id not in journals:
                raise ValidationError(_('The selected journal is not allowed for this partner state.'))
