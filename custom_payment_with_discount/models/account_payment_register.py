from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    cash_discount = fields.Monetary(
        string="Cash Discount",
        currency_field='currency_id',
        help="Cash discount granted while registering this payment.",
    )
    discount_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Discount Account",
        default=lambda self: self._default_discount_account_id(),
        domain="[('deprecated', '=', False)]",
        check_company=True,
        help="The account used to record cash discounts.",
    )

    def _default_discount_account_id(self):
        recent_payment = self.env['account.payment'].search(
            [('discount_account_id', '!=', False)],
            order='id desc',
            limit=1,
        )
        return recent_payment.discount_account_id

    @api.onchange('cash_discount')
    def _onchange_cash_discount(self):
        for wizard in self:
            if wizard.cash_discount < 0:
                raise ValidationError(_("Cash discount cannot be negative."))
            if not wizard.can_edit_wizard or not wizard.currency_id:
                continue
            total_amount = wizard._get_total_amounts_to_pay(wizard.batches)['amount_by_default']
            if wizard.currency_id.compare_amounts(wizard.cash_discount, total_amount) > 0:
                raise ValidationError(_("Cash discount cannot exceed the payment amount."))
            net_amount = total_amount - wizard.cash_discount
            wizard.amount = net_amount
            if wizard.cash_discount:
                wizard.custom_user_amount = net_amount
                wizard.custom_user_currency_id = wizard.currency_id
            else:
                wizard.custom_user_amount = False
                wizard.custom_user_currency_id = False

    def _add_cash_discount_vals(self, payment_vals):
        self.ensure_one()
        if not self.cash_discount:
            return payment_vals
        if self.cash_discount < 0:
            raise ValidationError(_("Cash discount cannot be negative."))
        if not self.discount_account_id:
            raise ValidationError(_("Discount account is required when cash discount is set."))
        total_amount = self._get_total_amounts_to_pay(self.batches)['amount_by_default']
        if self.currency_id.compare_amounts(self.cash_discount, total_amount) > 0:
            raise ValidationError(_("Cash discount cannot exceed the payment amount."))
        payment_vals.update({
            'amount': total_amount - self.cash_discount,
            'cash_discount': self.cash_discount,
            'discount_account_id': self.discount_account_id.id,
        })
        return payment_vals

    def _create_payment_vals_from_wizard(self, batch_result):
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        return self._add_cash_discount_vals(payment_vals)
