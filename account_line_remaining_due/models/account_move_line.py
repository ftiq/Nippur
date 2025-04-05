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
            move = line.move_id
            if not move:
                line.remaining_due = 0.0
                continue

            # نحدد سطر الزبون (حساب رقم 121)
            customer_line = move.line_ids.filtered(lambda l: l.account_id.code == '121')
            if not customer_line:
                line.remaining_due = 0.0
                continue

            # نتجاهل سطر الزبون نفسه
            if line.account_id.code == '121':
                line.remaining_due = 0.0
                continue

            # نجيب فقط السطور اللي حسابها مو 121
            target_lines = move.line_ids.filtered(lambda l: l.account_id.code != '121')
            total_amount = sum(abs(l.balance) for l in target_lines)

            # التوزيع من الزبون
            residual = customer_line[0].amount_residual
            line.remaining_due = (abs(line.balance) / total_amount) * residual if total_amount else 0.0
