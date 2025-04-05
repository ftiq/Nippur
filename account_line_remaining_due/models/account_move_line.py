from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    remaining_due = fields.Monetary(
        string="Remaining Due",
        compute="_compute_remaining_due",
        store=True,
        currency_field='currency_id',
    )

    @api.depends('move_id.line_ids.amount_residual')
    def _compute_remaining_due(self):
        for line in self:
            if line.account_id.account_type == 'income' and line.move_id:
                receivable_line = line.move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable'
                )
                if receivable_line:
                    total_due = receivable_line[0].amount_residual
                    total_sales = sum(
                        l.credit for l in line.move_id.line_ids.filtered(
                            lambda l: l.account_id.account_type == 'income'
                        )
                    )
                    line.remaining_due = (line.credit / total_sales) * total_due if total_sales else 0.0
                else:
                    line.remaining_due = 0.0
            else:
                line.remaining_due = 0.0
