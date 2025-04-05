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
        moves = self.mapped('move_id')
        for move in moves:
            # استخرج السطور المستهدفة فقط (كود الحساب 333 أو 400000)
            target_lines = move.line_ids.filtered(
                lambda l: str(l.account_id.code) in ('333', '400000')
            )

            if not target_lines:
                for line in move.line_ids:
                    line.remaining_due = 0.0
                continue

            # مجموع الدائن لجميع الأسطر المستهدفة
            total_sales = sum(l.credit for l in target_lines)
            # مجموع المتبقي من القيد كله
            total_due = sum(l.amount_residual for l in move.line_ids)

            for line in move.line_ids:
                if str(line.account_id.code) in ('333', '400000'):
                    line.remaining_due = (
                        (line.credit / total_sales) * total_due if total_sales else 0.0
                    )
                else:
                    line.remaining_due = 0.0
