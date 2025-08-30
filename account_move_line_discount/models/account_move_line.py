# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    discount_amount = fields.Monetary(
        string="الخصم",
        currency_field='currency_id',
        compute='_compute_discount_amount',
        store=True,
        help=""
    )

    net_amount = fields.Monetary(
        string="قبل الخصم",
        currency_field='currency_id',
        compute='_compute_net_amount',
        store=True,
        help=""
    )

    @api.depends('discount', 'price_unit', 'quantity', 'display_type')
    def _compute_discount_amount(self):

        for line in self:
            discount_amount = 0.0
            

            if (not line.display_type and line.discount > 0 and 
                line.price_unit > 0 and line.quantity > 0):
                line_total = line.price_unit * line.quantity
                discount_amount = line_total * (line.discount / 100.0)
            

            elif (line.price_unit < 0 and line.name and 
                  any(keyword in line.name.lower() for keyword in ['discount', 'خصم', 'تخفيض'])):
                discount_amount = abs(line.price_unit * line.quantity)
            
            line.discount_amount = discount_amount

    @api.depends('discount_amount', 'balance', 'name', 'price_unit', 'quantity')
    def _compute_net_amount(self):

        for line in self:
            if (line.price_unit < 0 and line.name and 
                any(keyword in line.name.lower() for keyword in ['discount', 'خصم', 'تخفيض'])):

                value = 0.0
            else:

                value = abs(line.balance) + (line.discount_amount or 0.0)
            line.net_amount = value
