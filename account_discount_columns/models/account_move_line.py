from odoo import fields, models, api

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    discount_amount = fields.Monetary(
        string="Discount Amount",
        currency_field='currency_id',
        compute="_compute_discount_amount",
        store=True,
    )

    @api.depends('price_unit', 'quantity', 'discount')
    def _compute_discount_amount(self):
        for line in self:
            if line.discount:
                line.discount_amount = (line.price_unit * line.quantity * line.discount) / 100
            else:
                line.discount_amount = 0.0
