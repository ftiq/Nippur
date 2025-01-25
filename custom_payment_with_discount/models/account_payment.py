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
        """
        Overrides the post method to include cash discount logic.
        Sets the journal entry to draft to allow modifications.
        """
        super(AccountPayment, self).action_post()

        for payment in self:
            if payment.cash_discount > 0 and payment.discount_account_id:
                # Ensure the journal entry exists
                move = payment.move_id
                if not move:
                    raise ValueError(_("No journal entry found for the payment."))

                # Set the journal entry to draft
                if move.state == 'posted':
                    move.button_draft()

                # Add the discount lines
                discount_line = {
                    'account_id': payment.discount_account_id.id,
                    'partner_id': payment.partner_id.id,
                    'name': 'Cash Discount',
                    'debit': payment.cash_discount if payment.payment_type == 'inbound' else 0.0,
                    'credit': payment.cash_discount if payment.payment_type == 'outbound' else 0.0,
                }
                receivable_discount_line = {
                    'account_id': payment.destination_account_id.id,
                    'partner_id': payment.partner_id.id,
                    'name': 'Receivable Adjustment for Discount',
                    'debit': 0.0 if payment.payment_type == 'inbound' else payment.cash_discount,
                    'credit': 0.0 if payment.payment_type == 'outbound' else payment.cash_discount,
                }

                # Write the discount lines to the journal entry
                move.write({
                    'line_ids': [
                        (0, 0, discount_line),
                        (0, 0, receivable_discount_line),
                    ]
                })

                # Repost the journal entry
                move.action_post()
