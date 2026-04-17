from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    ftiq_mobile_last_location_accuracy = fields.Float(copy=False)
    ftiq_mobile_last_location_is_mock = fields.Boolean(copy=False)
    ftiq_mobile_last_location_at = fields.Datetime(copy=False)
