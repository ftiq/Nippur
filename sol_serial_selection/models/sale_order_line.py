from odoo import api, fields, models

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    available_lots = fields.Many2many('stock.lot',compute="_compute_available_lot_ids")
    lot_ids = fields.Many2many('stock.lot', string='Lot/Serial Number', relation='sale_order_line_lot_rel', column1='sol_id', column2='lot_id', domain="[('id', 'in', available_lots)]")

    def write(self, vals):
        res = super().write(vals)
        update_needed = any(field in vals for field in ['product_uom_qty', 'lot_ids'])
        for line in self:
            if update_needed and line.order_id.state == 'sale':
                line.order_id._assign_serials_from_so()
        return res

    @api.depends('product_id')
    def _compute_available_lot_ids(self):
        StockQuant = self.env['stock.quant']
        for rec in self:
            if not rec.product_id or rec.product_id.tracking == 'none':
                rec.available_lots = self.env['stock.lot']
                continue
            quants = StockQuant.search([('product_id', '=', rec.product_id.id), ('lot_id', '!=', False), ('quantity', '>', 0), ('inventory_date', '!=', False)])
            rec.available_lots = quants.mapped('lot_id')

    @api.onchange('product_id', 'lot_ids')
    def _onchange_product_id(self):
        for rec in self:
            if rec.lot_ids:
                rec.product_uom_qty = len(rec.lot_ids.ids)