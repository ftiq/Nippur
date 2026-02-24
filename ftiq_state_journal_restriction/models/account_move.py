from odoo import api, models, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.onchange('partner_id')
    def _onchange_partner_id_ftiq_state_journal(self):
        for move in self:
            company = move.company_id or self.env.company
            if not company.ftiq_use_state_journal_restriction:
                continue
            state = move.partner_id.state_id
            if not state:
                continue
            journals = state.ftiq_journal_ids
            if not journals:
                continue
            if move.journal_id and move.journal_id in move.suitable_journal_ids:
                continue
            move.journal_id = move.suitable_journal_ids[:1]

    @api.depends('move_type', 'origin_payment_id', 'statement_line_id', 'partner_id', 'partner_id.state_id', 'company_id')
    def _compute_journal_id(self):
        super()._compute_journal_id()
        for move in self:
            company = move.company_id or self.env.company
            if not company.ftiq_use_state_journal_restriction:
                continue
            state = move.partner_id.state_id
            if not state:
                continue
            journals = state.ftiq_journal_ids
            if not journals:
                continue
            if move.journal_id and move.journal_id in move.suitable_journal_ids:
                continue
            move.journal_id = move.suitable_journal_ids[:1]

    @api.depends('company_id', 'invoice_filter_type_domain', 'partner_id', 'partner_id.state_id')
    def _compute_suitable_journal_ids(self):
        super()._compute_suitable_journal_ids()
        for move in self:
            company = move.company_id or self.env.company
            if not company.ftiq_use_state_journal_restriction:
                continue
            state = move.partner_id.state_id
            if not state:
                continue
            journals = state.ftiq_journal_ids
            if journals:
                move.suitable_journal_ids = move.suitable_journal_ids & journals

    @api.constrains('journal_id', 'partner_id')
    def _check_ftiq_state_journal(self):
        for move in self:
            company = move.company_id or self.env.company
            if not company.ftiq_use_state_journal_restriction:
                continue
            state = move.partner_id.state_id
            if not state:
                continue
            journals = state.ftiq_journal_ids
            if journals and move.journal_id not in journals:
                raise ValidationError(_('The selected journal is not allowed for this partner state.'))
