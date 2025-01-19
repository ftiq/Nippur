from odoo import models, fields

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    gift_quantity = fields.Float(string="Gift Quantity", default=0.0)
