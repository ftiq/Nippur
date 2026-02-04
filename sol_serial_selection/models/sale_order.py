from odoo import api, models

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super().action_confirm()
        self._assign_serials_from_so()
        return res

    def _assign_serials_from_so(self):
        for order in self:
            pickings = order.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel') and p.sale_id.id == order.id)
            for picking in pickings:
                for line in order.order_line:
                    if not line.lot_ids:
                        continue
                    moves = picking.move_ids.filtered(lambda m: m.product_id == line.product_id)
                    if not moves:
                        continue
                    StockQuant = self.env['stock.quant'].search([('product_id', '=', line.product_id.id), ('lot_id', 'in', line.lot_ids.ids),('quantity', '>', 0), ('inventory_date', '!=', False)])
                    for move in moves:
                        move.move_line_ids.unlink()
                        for lot in line.lot_ids:
                            quant = StockQuant.filtered(lambda q: q.lot_id == lot)
                            if quant:
                                self.env['stock.move.line'].create({ 'quant_id': quant.id,
                                    'move_id': move.id, 'product_id': move.product_id.id,
                                    'lot_id': quant.lot_id.id, 'quantity': quant.quantity,
                                    'location_id': quant.location_id.id, 'location_dest_id': move.location_dest_id.id, })