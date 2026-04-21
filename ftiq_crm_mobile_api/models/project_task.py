from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


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
        string="Task Type",
        copy=False,
    )
    ftiq_mobile_visit_state = fields.Selection(
        [
            ("not_started", "Not Started"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        string="Visit Status",
        default="not_started",
        copy=False,
    )
    ftiq_mobile_started_at = fields.Datetime(string="Started At", copy=False)
    ftiq_mobile_completed_at = fields.Datetime(string="Completed At", copy=False)
    ftiq_mobile_start_latitude = fields.Float(
        string="Start Latitude",
        digits=(16, 6),
        copy=False,
    )
    ftiq_mobile_start_longitude = fields.Float(
        string="Start Longitude",
        digits=(16, 6),
        copy=False,
    )
    ftiq_mobile_start_accuracy = fields.Float(string="Start Accuracy", copy=False)
    ftiq_mobile_start_is_mock = fields.Boolean(string="Start Is Mock", copy=False)
    ftiq_mobile_end_latitude = fields.Float(
        string="End Latitude",
        digits=(16, 6),
        copy=False,
    )
    ftiq_mobile_end_longitude = fields.Float(
        string="End Longitude",
        digits=(16, 6),
        copy=False,
    )
    ftiq_mobile_end_accuracy = fields.Float(string="End Accuracy", copy=False)
    ftiq_mobile_end_is_mock = fields.Boolean(string="End Is Mock", copy=False)
    ftiq_mobile_execution_payload = fields.Text(string="Execution Data", copy=False)
    ftiq_mobile_request_uid = fields.Char(string="Request UID", copy=False, index=True)

    ftiq_mobile_latitude = fields.Float(string="Latitude", digits=(16, 6), copy=False)
    ftiq_mobile_longitude = fields.Float(string="Longitude", digits=(16, 6), copy=False)
    ftiq_mobile_accuracy = fields.Float(string="Accuracy", copy=False)
    ftiq_mobile_is_mock = fields.Boolean(string="Is Mock", copy=False)
    ftiq_mobile_location_at = fields.Datetime(string="Recorded At", copy=False)

    @api.constrains("ftiq_mobile_task_type", "partner_id")
    def _check_mobile_task_partner(self):
        for task in self:
            if task.ftiq_mobile_task_type and not task.partner_id:
                raise ValidationError(_("Client is required when a task type is selected."))

    @api.constrains("ftiq_mobile_task_type", "project_id")
    def _check_mobile_task_fsm_project(self):
        for task in self:
            if not task.ftiq_mobile_task_type or not task.project_id:
                continue
            if "is_fsm" in task.project_id._fields and not task.project_id.is_fsm:
                raise ValidationError(_("Mobile task types can only be used on field service projects."))

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

    def _ftiq_mobile_has_standard_timer(self):
        self.ensure_one()
        return (
            "user_timer_id" in self._fields
            and callable(getattr(type(self), "action_timer_start", None))
            and self.env.registry.get("timer.timer")
        )

    def _ftiq_mobile_start_standard_timer(self):
        self.ensure_one()
        if not self._ftiq_mobile_has_standard_timer():
            return False
        timer = self.user_timer_id
        if timer and timer.timer_start and not timer.timer_pause:
            return True
        self.with_context(
            fsm_mode=bool("is_fsm" in self._fields and self.is_fsm),
            default_project_id=self.project_id.id,
        ).action_timer_start()
        timer = self.user_timer_id
        return bool(timer and timer.timer_start)

    def _ftiq_mobile_stop_standard_timer(self, description=None):
        self.ensure_one()
        if not self._ftiq_mobile_has_standard_timer():
            return False
        timer = self.user_timer_id
        if not timer or not timer.timer_start:
            return False

        minutes_spent = timer._get_minutes_spent()
        rounded_hours = minutes_spent / 60.0
        if callable(getattr(type(self), "_get_rounded_hours", None)):
            rounded_hours = self._get_rounded_hours(minutes_spent)

        if rounded_hours <= 0:
            timer.unlink()
            return False

        timesheet_wizard_model = self.env.registry.get("project.task.create.timesheet")
        if timesheet_wizard_model:
            wizard_values = {
                "task_id": self.id,
                "time_spent": rounded_hours,
            }
            description = (description or self.name or "").strip()
            if description:
                wizard_values["description"] = description
            wizard = self.env["project.task.create.timesheet"].with_context(
                fsm_mode=bool("is_fsm" in self._fields and self.is_fsm),
                default_project_id=self.project_id.id,
                default_task_id=self.id,
                active_id=self.id,
            ).create(wizard_values)
            return wizard.save_timesheet()

        timer.action_timer_stop()
        timer.unlink()
        return rounded_hours
