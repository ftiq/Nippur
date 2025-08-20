from odoo import api, fields, models

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    discount_amount = fields.Monetary(
        string='Discount Amount',
        compute='_compute_discount_amounts',
        store=True,
        currency_field='currency_id',
    )

    gross_total = fields.Monetary(
        string='Gross Total',
        compute='_compute_discount_amounts',
        store=True,
        currency_field='currency_id',
    )

    @api.depends('price_unit', 'quantity', 'discount', 'currency_id')
    def _compute_discount_amounts(self):
        for line in self:
            currency = line.currency_id

            # تجاهل أسطر الملاحظات/العناوين
            if line.display_type:
                line.discount_amount = 0.0
                line.gross_total = 0.0
                continue

            # المبلغ الخام
            raw_amount = line.price_unit * line.quantity if line.price_unit and line.quantity else 0.0

            if line.price_unit < 0:  
                # هذا سطر خصم (سعر بالسالب)
                disc = abs(raw_amount)
                line.discount_amount = currency.round(disc) if currency else disc
                line.gross_total = 0.0
            else:
                # سطر عادي: خصم بالنسبة (لو موجود)
                disc = raw_amount * (line.discount / 100.0) if line.discount else 0.0
                gross = raw_amount + disc
                line.discount_amount = currency.round(disc) if currency else disc
                line.gross_total = currency.round(gross) if currency else gross
