from odoo import models, fields, api, _

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
        super(AccountPayment, self).action_post()

        for payment in self:
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

            # Add cash discount lines if applicable
            if payment.cash_discount > 0 and payment.discount_account_id:
                # Remove existing discount lines to avoid duplication
                move.line_ids.filtered(lambda l: l.account_id == payment.discount_account_id or l.account_id == payment.destination_account_id and l.name in ['Cash Discount', 'Receivable Adjustment for Discount']).unlink()

                # Define amounts
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
                else:  # outbound
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

                # Create the new discount lines
                move.with_context(skip_account_move_synchronization=True).write({
                    'line_ids': [(0, 0, debit_line_vals), (0, 0, credit_line_vals)]
                })

            move.action_post()
