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

            # نحدد سطر حساب الزبون فقط (رقم الحساب = 121)
            customer_line = move.line_ids.filtered(lambda l: l.account_id.code == '121')
            if not customer_line:
                line.remaining_due = 0.0
                continue

            # ما نحسب شيء في سطر الزبون نفسه
            if line.account_id.code == '121':
                line.remaining_due = 0.0
                continue

            # نوزّع على كل السطور ما عدا الزبون
            target_lines = move.line_ids.filtered(lambda l: l.account_id.code != '121')
            total_amount = sum(abs(l.balance) for l in target_lines)

            # نوزّع المتبقي (residual) من حساب الزبون على الباقين
            residual = customer_line[0].amount_residual
            line.remaining_due = (abs(line.balance) / total_amount) * residual if total_amount else 0.0
