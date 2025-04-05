from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    remaining_due = fields.Monetary(
        string='Remaining Due',
        currency_field='currency_id',
        compute='_compute_remaining_due',
        store=True
    )

    @api.depends('move_id.line_ids.amount_residual')
    def _compute_remaining_due(self):
        for line in self:
            if line.move_id:
                move = line.move_id

                # تحديد السطر الذي يحمل حساب الزبون فقط (account_id = 121)
                customer_line = move.line_ids.filtered(lambda l: l.account_id.id == 121)

                # كل الأسطر باستثناء حساب الزبون
                other_lines = move.line_ids.filtered(lambda l: l.account_id.id != 121)

                if customer_line and other_lines:
                    residual = customer_line[0].amount_residual
                    total_credit = sum(l.credit for l in other_lines)
                    if total_credit:
                        line.remaining_due = (line.credit / total_credit) * residual if line in other_lines else 0.0
                    else:
                        line.remaining_due = 0.0
                else:
                    line.remaining_due = 0.0
