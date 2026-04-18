from odoo import _, api, fields, models
from odoo.exceptions import UserError


_MOBILE_LOCATION_FIELDS = {
    "partner_latitude",
    "partner_longitude",
    "ftiq_mobile_last_location_accuracy",
    "ftiq_mobile_last_location_is_mock",
    "ftiq_mobile_last_location_at",
}


class ResPartner(models.Model):
    _inherit = "res.partner"

    ftiq_mobile_last_location_accuracy = fields.Float(copy=False)
    ftiq_mobile_last_location_is_mock = fields.Boolean(copy=False)
    ftiq_mobile_last_location_at = fields.Datetime(copy=False)

    def _check_mobile_location_write(self, vals):
        if self.env.context.get("ftiq_mobile_location_write"):
            return
        if _MOBILE_LOCATION_FIELDS.intersection(vals):
            raise UserError(_("Mobile location values can only be updated from the mobile application."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_mobile_location_write(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._check_mobile_location_write(vals)
        return super().write(vals)
