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
            # ✅ إذا الحساب income أو كوده 333
            if (line.account_id.account_type == 'income' or str(line.account_id.code) == '333') and line.move_id:
                # نبحث عن سطور الزبون (ذمم مدينة)
                receivable_lines = line.move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable'
                )

                if receivable_lines:
                    total_due = sum(l.amount_residual for l in receivable_lines)

                    # ✅ نحسب فقط الأسطر income أو كودها 333
                    total_sales = sum(
                        l.credit for l in line.move_id.line_ids.filtered(
                            lambda l: l.account_id.account_type == 'income' or str(l.account_id.code) == '333'
                        )
                    )

                    line.remaining_due = (line.credit / total_sales) * total_due if total_sales else 0.0
                else:
                    line.remaining_due = 0.0
            else:
                line.remaining_due = 0.0
