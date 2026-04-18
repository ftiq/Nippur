from odoo import models, fields, _

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    cash_discount = fields.Monetary(
        string="Cash Discount",
        currency_field='currency_id',
        help="The cash discount to apply for this payment."
    )
    discount_account_id = fields.Many2one(
        'account.account',
        string="Discount Account",
        help="The account used to record cash discounts."
    )

    def action_post(self):
        result = super().action_post()

        for payment in self.filtered(lambda item: item.cash_discount > 0 and item.discount_account_id):
            move = payment.move_id
            if not move:
                raise ValueError(_("No journal entry found for the payment."))

            memo = payment.memo or 'Payment'

            if move.state == 'posted':
                move.button_draft()

            # Update empty line names
            for line in move.line_ids:
                if not line.name or line.name == '/':
                    line.name = memo

            # Remove existing discount lines to avoid duplication.
            move.line_ids.filtered(
                lambda line: (
                    line.account_id == payment.discount_account_id
                    and line.name == 'Cash Discount'
                ) or (
                    line.account_id == payment.destination_account_id
                    and line.name == 'Receivable Adjustment for Discount'
                )
            ).unlink()

            discount_amount = payment.cash_discount
            if payment.payment_type == 'inbound':
                debit_line_vals = {
                    'name': 'Cash Discount',
                    'account_id': payment.discount_account_id.id,
                    'debit': discount_amount,
                    'credit': 0.0,
                }
                credit_line_vals = {
                    'name': 'Receivable Adjustment for Discount',
                    'account_id': payment.destination_account_id.id,
                    'debit': 0.0,
                    'credit': discount_amount,
                }
            else:
                debit_line_vals = {
                    'name': 'Receivable Adjustment for Discount',
                    'account_id': payment.destination_account_id.id,
                    'debit': discount_amount,
                    'credit': 0.0,
                }
                credit_line_vals = {
                    'name': 'Cash Discount',
                    'account_id': payment.discount_account_id.id,
                    'debit': 0.0,
                    'credit': discount_amount,
                }

            move.with_context(skip_account_move_synchronization=True).write({
                'line_ids': [(0, 0, debit_line_vals), (0, 0, credit_line_vals)]
            })

            move.action_post()

        return result
