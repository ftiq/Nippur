from odoo import _, api, fields, models
from odoo.exceptions import UserError


_MOBILE_LOCATION_FIELDS = {
    "ftiq_mobile_latitude",
    "ftiq_mobile_longitude",
    "ftiq_mobile_accuracy",
    "ftiq_mobile_is_mock",
    "ftiq_mobile_location_at",
}


class AccountPayment(models.Model):
    _inherit = "account.payment"

    ftiq_mobile_task_id = fields.Many2one(
        "project.task",
        string="Field Service Task",
        index=True,
        copy=False,
        ondelete="set null",
    )
    ftiq_mobile_latitude = fields.Float(digits=(16, 6), copy=False)
    ftiq_mobile_longitude = fields.Float(digits=(16, 6), copy=False)
    ftiq_mobile_accuracy = fields.Float(copy=False)
    ftiq_mobile_is_mock = fields.Boolean(copy=False)
    ftiq_mobile_location_at = fields.Datetime(copy=False)

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
