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
            customer_lines = move.line_ids.filtered(lambda l: l.account_id.code == '121')
            target_lines = move.line_ids.filtered(
                lambda l: (l.account_id.code.startswith('400') or l.name == 'رصيد أفتتاحي')
            )

            if not customer_lines or not target_lines:
                for line in move.line_ids:
                    line.remaining_due = 0.0
                continue

            residual = customer_lines[0].amount_residual
            total_amount = sum(abs(l.balance) for l in target_lines)

            for line in move.line_ids:
                if line.account_id.code == '121':
                    line.remaining_due = 0.0
                elif line.name == 'رصيد أفتتاحي':
                    line.remaining_due = 0.0
                    line.credit = residual
                elif line.account_id.code.startswith('400'):
                    line.remaining_due = (
                        (abs(line.balance) / total_amount) * residual
                        if total_amount else 0.0
                    )
                else:
                    line.remaining_due = 0.0
