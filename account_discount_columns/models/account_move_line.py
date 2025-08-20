# -*- coding: utf-8 -*-
from odoo import api, fields, models

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    discount_amount = fields.Monetary(
        string='Discount Amount',
        compute='_compute_discount_amounts',
        store=True,
        currency_field='currency_id',
        help="The total discount amount for this line"
    )

    gross_total = fields.Monetary(
        string='Gross Total',
        compute='_compute_discount_amounts',
        store=True,
        currency_field='currency_id',
        help="Total amount before discount (Net + Discount)"
    )

    @api.depends('price_unit', 'quantity', 'discount', 'currency_id', 'display_type')
    def _compute_discount_amounts(self):
        for line in self:
            # تجاهل أسطر العناوين/الملاحظات
            if line.display_type:
                line.discount_amount = 0.0
                line.gross_total = 0.0
                continue

            # إذا لا توجد قيم أرقام كافية
            if not line.price_unit or not line.quantity:
                line.discount_amount = 0.0
                line.gross_total = 0.0
                continue

            # المبلغ الخام قبل أي خصم
            raw_amount = line.price_unit * line.quantity
            currency = line.currency_id

            # 1) سطر خصم (قيمة سالبة): اعتبر القيمة المطلقة هي مبلغ الخصم
            if raw_amount < 0:
                disc = abs(raw_amount)
                line.discount_amount = currency.round(disc) if currency else disc
                # هذا سطر خصم، لا يوجد إجمالي خام لهذا السطر
                line.gross_total = 0.0
            else:
                # 2) سطر عادي: احسب خصم النسبة إن وُجد
                disc = raw_amount * (line.discount / 100.0) if line.discount else 0.0
                gross = raw_amount + disc
                line.discount_amount = currency.round(disc) if currency else disc
                line.gross_total = currency.round(gross) if currency else gross
