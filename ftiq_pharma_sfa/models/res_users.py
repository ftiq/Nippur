from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    ftiq_area_id = fields.Many2one('ftiq.area')
    ftiq_city_id = fields.Many2one('ftiq.city')
    ftiq_is_medical_rep = fields.Boolean(default=False)
    ftiq_supervisor_id = fields.Many2one('res.users')
