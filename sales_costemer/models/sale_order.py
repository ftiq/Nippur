from odoo import models, fields

class SaleOrder(models.Model):
    _inherit = "sale.order"

    representative_id = fields.Many2one('res.users', string="Sales Representative")
