from odoo import _, api, fields, models
from odoo.exceptions import UserError


_MOBILE_LOCATION_FIELDS = {
    "ftiq_mobile_latitude",
    "ftiq_mobile_longitude",
    "ftiq_mobile_accuracy",
    "ftiq_mobile_is_mock",
    "ftiq_mobile_location_at",
    "ftiq_mobile_visit_state",
    "ftiq_mobile_started_at",
    "ftiq_mobile_completed_at",
    "ftiq_mobile_start_latitude",
    "ftiq_mobile_start_longitude",
    "ftiq_mobile_start_accuracy",
    "ftiq_mobile_start_is_mock",
    "ftiq_mobile_end_latitude",
    "ftiq_mobile_end_longitude",
    "ftiq_mobile_end_accuracy",
    "ftiq_mobile_end_is_mock",
    "ftiq_mobile_execution_payload",
    "ftiq_mobile_request_uid",
}


class ProjectTask(models.Model):
    _inherit = "project.task"

    ftiq_mobile_task_type = fields.Selection(
        [
            ("field_visit", "Field Visit"),
            ("collection", "Collection"),
            ("sales_order", "Sales Order"),
            ("stock_audit", "Customer Stock Audit"),
        ],
        string="Mobile Task Type",
        copy=False,
    )
    ftiq_mobile_visit_state = fields.Selection(
        [
            ("not_started", "Not Started"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        string="Mobile Visit State",
        default="not_started",
        copy=False,
    )
    ftiq_mobile_started_at = fields.Datetime(copy=False)
    ftiq_mobile_completed_at = fields.Datetime(copy=False)
    ftiq_mobile_start_latitude = fields.Float(digits=(16, 6), copy=False)
    ftiq_mobile_start_longitude = fields.Float(digits=(16, 6), copy=False)
    ftiq_mobile_start_accuracy = fields.Float(copy=False)
    ftiq_mobile_start_is_mock = fields.Boolean(copy=False)
    ftiq_mobile_end_latitude = fields.Float(digits=(16, 6), copy=False)
    ftiq_mobile_end_longitude = fields.Float(digits=(16, 6), copy=False)
    ftiq_mobile_end_accuracy = fields.Float(copy=False)
    ftiq_mobile_end_is_mock = fields.Boolean(copy=False)
    ftiq_mobile_execution_payload = fields.Text(copy=False)
    ftiq_mobile_request_uid = fields.Char(copy=False, index=True)

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
