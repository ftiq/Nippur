from odoo import api, fields, models

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
            if line.account_id.account_type == 'income' and line.move_id:
                move = line.move_id

                # سطر الزبون، باستثناء الحساب 7
                customer_line = move.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable' and l.account_id.id != 7
                )

                # جميع خطوط المبيعات
                sales_lines = move.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'income'
                )

                if customer_line and sales_lines:
                    total_credit = sum(l.credit for l in sales_lines)
                    residual = customer_line[0].amount_residual
                    line.remaining_due = (line.credit / total_credit) * residual if total_credit else 0.0
                else:
                    line.remaining_due = 0.0
            else:
                line.remaining_due = 0.0
