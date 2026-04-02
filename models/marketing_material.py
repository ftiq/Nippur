from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FtiqMarketingMaterial(models.Model):
    _name = 'ftiq.marketing.material'
    _description = 'Marketing Material'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    product_id = fields.Many2one('product.product', ondelete='cascade')
    call_reason_id = fields.Many2one('ftiq.call.reason')
    material_scope = fields.Selection([
        ('product', 'Product Detailing'),
        ('visit', 'Visit Level'),
        ('both', 'Product or Visit'),
    ], default='product', required=True)
    material_type = fields.Selection([
        ('visual', 'Visual Aid'),
        ('brochure', 'Brochure'),
        ('pdf', 'PDF'),
        ('video', 'Video'),
        ('sample', 'Sample Guide'),
    ], default='visual', required=True)
    image = fields.Binary(attachment=True)
    file = fields.Binary(attachment=True)
    file_name = fields.Char()
    description = fields.Text()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    @api.constrains('material_scope', 'product_id')
    def _check_product_requirement(self):
        for rec in self:
            if rec.material_scope == 'product' and not rec.product_id:
                raise ValidationError(_('Product-scoped marketing material must be linked to a product.'))
