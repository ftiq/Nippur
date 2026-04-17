from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    ftiq_mobile_latitude = fields.Float(digits=(16, 6), copy=False)
    ftiq_mobile_longitude = fields.Float(digits=(16, 6), copy=False)
    ftiq_mobile_accuracy = fields.Float(copy=False)
    ftiq_mobile_is_mock = fields.Boolean(copy=False)
    ftiq_mobile_location_at = fields.Datetime(copy=False)
