from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.onchange('partner_id')
    def _onchange_partner_id_set_warehouse(self):
        """
        Dynamically set the warehouse_id based on the selected partner's x_studio_warehouse field.
        """
        if self.partner_id and self.partner_id.x_studio_warehouse:
            # Use the partner's defined warehouse
            self.warehouse_id = self.partner_id.x_studio_warehouse.id
        else:
            # Fallback to the first available warehouse
            default_warehouse = self.env['stock.warehouse'].search([], limit=1)
            self.warehouse_id = default_warehouse.id if default_warehouse else False
