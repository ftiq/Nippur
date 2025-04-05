@api.depends('move_id.line_ids.amount_residual')
def _compute_remaining_due(self):
    for line in self:
        if line.account_id.account_type == 'income' and line.move_id:
            move = line.move_id
            customer_line = move.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
            sales_lines = move.line_ids.filtered(lambda l: l.account_id.account_type == 'income')

            if customer_line and sales_lines:
                total_credit = sum(l.credit for l in sales_lines)
                residual = customer_line[0].amount_residual

                line.remaining_due = (line.credit / total_credit) * residual if total_credit else 0.0
            else:
                line.remaining_due = 0.0
        else:
            line.remaining_due = 0.0
