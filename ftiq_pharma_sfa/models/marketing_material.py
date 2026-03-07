from odoo import models, fields


class FtiqMarketingMaterial(models.Model):
    _name = 'ftiq.marketing.material'
    _description = 'Marketing Material'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    product_id = fields.Many2one('product.product', required=True, ondelete='cascade')
    image = fields.Binary(attachment=True)
    file = fields.Binary(attachment=True)
    file_name = fields.Char()
    description = fields.Text()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
