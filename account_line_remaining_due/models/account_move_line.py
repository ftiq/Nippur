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

            # سطر الزبون (حساب 121 فقط)
            customer_line = move.line_ids.filtered(lambda l: l.account_id.code == '121')
            if not customer_line:
                line.remaining_due = 0.0
                continue

            # تجاهل السطر إذا هو نفسه سطر الزبون
            if line.account_id.code == '121':
                line.remaining_due = 0.0
                continue

            # باقي الأسطر (اللي مش 121)
            lines_to_distribute = move.line_ids.filtered(lambda l: l.account_id.code != '121')
            total_credit = sum(l.credit for l in lines_to_distribute)

            # المتبقي في سطر الزبون
            residual = customer_line[0].amount_residual

            # توزيع المتبقي على حسب نسبة الائتمان
            line.remaining_due = (line.credit / total_credit) * residual if total_credit else 0.0
