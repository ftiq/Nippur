from odoo import api, fields, models

class AccountMove(models.Model):
    _inherit = 'account.move'

    total_discount = fields.Monetary(
        string="إجمالي الخصم",
        compute="_compute_total_discount",
        store=True,
        currency_field="currency_id"
    )

    @api.depends('invoice_line_ids.product_id', 'invoice_line_ids.price_subtotal')
    def _compute_total_discount(self):
        DISCOUNT_PRODUCT_ID = 9   # رقم المنتج الخاص بالخصم

        for move in self:
            discount_total = 0.0
            for line in move.invoice_line_ids:
                if line.product_id and line.product_id.id == DISCOUNT_PRODUCT_ID:
                    discount_total += abs(line.price_subtotal)
            move.total_discount = discount_total
