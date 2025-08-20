# -*- coding: utf-8 -*-
from odoo import api, fields, models

DISCOUNT_PRODUCT_ID = 9  # رقم منتج الخصم

class AccountMove(models.Model):
    _inherit = "account.move"

    total_discount = fields.Monetary(
        string="إجمالي الخصم",
        compute="_compute_total_discount",
        store=False,                     # غير مخزن لتظهر القيمة فوراً
        currency_field="currency_id",
        help="إجمالي الخصم المجمع من أسطر الفاتورة المرتبطة بالمنتج رقم 9."
    )

    @api.depends(
        "invoice_line_ids.product_id",
        "invoice_line_ids.price_subtotal",
        "invoice_line_ids.display_type",
        "currency_id",
        "move_type",
    )
    def _compute_total_discount(self):
        for move in self:
            # نحسب فقط من أسطر الفاتورة الحقيقية (وليس قسم/ملاحظة)
            lines = move.invoice_line_ids.filtered(
                lambda l: not l.display_type and l.product_id and l.product_id.id == DISCOUNT_PRODUCT_ID
            )
            total = sum(abs(l.price_subtotal or 0.0) for l in lines)
            move.total_discount = move.currency_id.round(total) if move.currency_id else total
