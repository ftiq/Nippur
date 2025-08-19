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

    @api.depends('price_unit', 'quantity', 'discount', 'currency_id')
    def _compute_discount_amounts(self):

        for line in self:
            if line.price_unit and line.quantity and line.discount:
                gross_amount = line.price_unit * line.quantity
                
                discount_amount = gross_amount * (line.discount / 100.0)
                
                line.discount_amount = line.currency_id.round(discount_amount) if line.currency_id else discount_amount
                line.gross_total = line.currency_id.round(gross_amount) if line.currency_id else gross_amount
            else:
                line.discount_amount = 0.0
                line.gross_total = line.currency_id.round(line.price_unit * line.quantity) if line.currency_id and line.price_unit and line.quantity else 0.0
