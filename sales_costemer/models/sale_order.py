from odoo import models, fields, api # type: ignore

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    representative_id = fields.Many2one(
        'res.users',
        string='Sales Representative',
        help='Assign a sales representative to this order.',
    )
    gift_line_ids = fields.One2many(
        'sale.order.gift.line', 'sale_order_id',
        string='Gifts',
        help='List of gift products included in this sale order.'
    )

class SaleOrderGiftLine(models.Model):
    _name = 'sale.order.gift.line'
    _description = 'Sale Order Gift Line'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Gift Product', required=True)
    quantity = fields.Float(string='Gift Quantity', default=1.0, required=True)
