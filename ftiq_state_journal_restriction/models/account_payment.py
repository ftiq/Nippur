from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    ftiq_allowed_journal_ids = fields.Many2many(
        comodel_name='account.journal',
        compute='_compute_ftiq_allowed_journal_ids',
    )

    def _ftiq_get_allowed_journals(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        if not company.ftiq_use_state_journal_restriction:
            return self.env['account.journal']

        partner = self.partner_id
        state = partner.state_id or partner.commercial_partner_id.state_id
        if not state or not state.ftiq_journal_ids:
            return self.env['account.journal']

        journals = self.env['account.journal'].search([
            '|',
            ('company_id', 'parent_of', company.id),
            ('company_id', 'child_of', company.id),
            ('type', 'in', ('bank', 'cash', 'credit')),
        ])
        journals &= state.ftiq_journal_ids

        if self.payment_type == 'inbound':
            journals = journals.filtered('inbound_payment_method_line_ids')
        elif self.payment_type == 'outbound':
            journals = journals.filtered('outbound_payment_method_line_ids')

        return journals

    @api.depends('payment_type', 'partner_id', 'partner_id.state_id', 'partner_id.commercial_partner_id.state_id', 'company_id')
    def _compute_ftiq_allowed_journal_ids(self):
        for pay in self:
            company = pay.company_id or pay.env.company
            if not company.ftiq_use_state_journal_restriction:
                pay.ftiq_allowed_journal_ids = pay.available_journal_ids
                continue
            pay.ftiq_allowed_journal_ids = pay._ftiq_get_allowed_journals()

    def _ftiq_get_restricted_available_journals(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        if not company.ftiq_use_state_journal_restriction:
            return self.env['account.journal']
        return self._ftiq_get_allowed_journals()

    @api.depends('payment_type', 'partner_id', 'partner_id.state_id', 'partner_id.commercial_partner_id.state_id', 'company_id')
    def _compute_available_journal_ids(self):
        super()._compute_available_journal_ids()
        for pay in self:
            company = pay.company_id or self.env.company
            if not company.ftiq_use_state_journal_restriction:
                continue
            pay.available_journal_ids = pay._ftiq_get_allowed_journals()

    @api.depends('company_id', 'partner_id', 'partner_id.state_id', 'partner_id.commercial_partner_id.state_id', 'payment_type', 'ftiq_allowed_journal_ids')
    def _compute_journal_id(self):
        super()._compute_journal_id()
        for pay in self:
            company = pay.company_id or pay.env.company
            if not company.ftiq_use_state_journal_restriction:
                continue
            partner = pay.partner_id
            state = partner.state_id or partner.commercial_partner_id.state_id

            if not state or not state.ftiq_journal_ids:
                pay.journal_id = False
                continue

            allowed = pay.ftiq_allowed_journal_ids
            if not allowed:
                pay.journal_id = False
                continue

            if pay.journal_id and pay.journal_id in allowed:
                continue

            pay.journal_id = allowed[:1]

    @api.constrains('journal_id', 'partner_id', 'company_id')
    def _check_ftiq_state_journal(self):
        for pay in self:
            company = pay.company_id or self.env.company
            partner = pay.partner_id
            state = partner.state_id or partner.commercial_partner_id.state_id
            if not company.ftiq_use_state_journal_restriction or not state or not state.ftiq_journal_ids:
                continue
            allowed = pay._ftiq_get_allowed_journals()
            if pay.journal_id and allowed and pay.journal_id not in allowed:
                raise ValidationError(_('The selected journal is not allowed for this partner state.'))

    @api.onchange('partner_id', 'payment_type', 'company_id')
    def _onchange_ftiq_state_journal(self):
        company = self.company_id or self.env.company
        if not company.ftiq_use_state_journal_restriction:
            return
        allowed = self._ftiq_get_allowed_journals()
        res = {'domain': {'journal_id': [('id', 'in', allowed.ids)]}}
        if not allowed:
            self.journal_id = False
            return res
        if self.journal_id not in allowed:
            self.journal_id = allowed[:1]
        return res
