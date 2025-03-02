from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    custom_amount = fields.Monetary(
        compute='_compute_custom_amount',
        string='Custom Amount',
        currency_field='currency_id',
        store=True
    )

    @api.depends('amount_currency', 'debit', 'credit')
    def _compute_custom_amount(self):
        for line in self:
            if line.currency_id:
                line.custom_amount = line.amount_currency
            else:
                line.custom_amount = line.debit - line.credit
