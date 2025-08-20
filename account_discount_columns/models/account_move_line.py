from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    discount_amount = fields.Monetary(
        string="Discount Amount",
        currency_field="currency_id",
        compute="_compute_discount_amount",
        store=True
    )

    gross_total = fields.Monetary(
        string="Gross Total",
        currency_field="currency_id",
        compute="_compute_gross_total",
        store=True
    )

    @api.depends("discount", "price_unit", "quantity")
    def _compute_discount_amount(self):
        for line in self:
            # حساب مبلغ الخصم = (السعر * الكمية * نسبة الخصم)
            line.discount_amount = (line.price_unit * line.quantity * line.discount) / 100.0

    @api.depends("price_unit", "quantity")
    def _compute_gross_total(self):
        for line in self:
            # الإجمالي قبل الخصم = السعر * الكمية
            line.gross_total = line.price_unit * line.quantity
