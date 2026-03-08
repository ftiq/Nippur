from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .task_profile import TASK_PROFILE_CODES


FTIQ_TASK_TERMINAL_STATES = ("completed", "confirmed", "cancelled")


class FtiqDailyTask(models.Model):
    _inherit = "ftiq.daily.task"

    task_profile_id = fields.Many2one(
        "ftiq.task.profile",
        string="Task Profile",
        default=lambda self: self.env["ftiq.task.profile"].get_default_profile("visit"),
        tracking=True,
        ondelete="restrict",
    )
    task_type = fields.Selection(TASK_PROFILE_CODES, string="Task Type", required=True, default="visit", tracking=True)
    partner_id = fields.Many2one("res.partner", string="Client", tracking=True)
    state = fields.Selection(
        selection_add=[
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("confirmed", "Confirmed"),
            ("returned", "Returned"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )

    requires_partner = fields.Boolean(related="task_profile_id.requires_partner", store=True, readonly=True)
    requires_associated_partner = fields.Boolean(
        related="task_profile_id.requires_associated_partner", store=True, readonly=True
    )
    requires_user = fields.Boolean(related="task_profile_id.requires_user", store=True, readonly=True)
    requires_products = fields.Boolean(related="task_profile_id.requires_products", store=True, readonly=True)
    requires_check_in = fields.Boolean(related="task_profile_id.requires_check_in", store=True, readonly=True)
    requires_photos = fields.Boolean(related="task_profile_id.requires_photos", store=True, readonly=True)
    required_photo_count = fields.Integer(related="task_profile_id.required_photo_count", store=True, readonly=True)
    confirmation_required = fields.Boolean(
        related="task_profile_id.requires_confirmation", store=True, readonly=True
    )
    allow_manual_completion = fields.Boolean(
        related="task_profile_id.allow_manual_completion", store=True, readonly=True
    )

    @api.onchange("task_profile_id")
    def _onchange_task_profile_id(self):
        for rec in self.filtered("task_profile_id"):
            rec.task_type = rec.task_profile_id.code

    @api.onchange("task_type")
    def _onchange_task_type(self):
        for rec in self:
            if rec.task_profile_id and rec.task_profile_id.code == rec.task_type:
                continue
            rec.task_profile_id = self.env["ftiq.task.profile"].get_default_profile(rec.task_type)

    @api.constrains("task_profile_id", "partner_id", "associated_partner_id", "user_id")
    def _check_task_profile_requirements(self):
        for rec in self:
            if rec.requires_partner and not rec.partner_id:
                raise UserError(_("A client is required for this task profile."))
            if rec.requires_associated_partner and not rec.associated_partner_id:
                raise UserError(_("An associated client is required for this task profile."))
            if rec.requires_user and not rec.user_id:
                raise UserError(_("A representative is required for this task profile."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._sync_profile_vals(vals, apply_default=True)
            if not vals.get("state"):
                vals["state"] = self._default_state_from_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        self._sync_profile_vals(vals, apply_default=False)
        return super().write(vals)

    def action_start(self):
        for rec in self:
            if rec.state not in ("draft", "pending", "returned"):
                raise UserError(_("Only draft, pending, or returned tasks can be started."))
            rec._validate_profile_requirements_for_execution()
            rec._capture_location_from_context()
            rec._ensure_execution_attendance()
        self.write({"state": "in_progress"})

    def action_complete(self):
        for rec in self:
            if rec.state != "in_progress":
                raise UserError(_("Only tasks in progress can be completed."))
            rec._capture_location_from_context()
            rec._validate_completion_dependencies()
            rec.write({
                "state": "submitted" if rec.confirmation_required else "completed",
                "completed_date": fields.Datetime.now(),
            })

    def action_submit(self):
        for rec in self:
            if not rec.confirmation_required:
                raise UserError(_("This task profile does not require submission."))
            if rec.state not in ("in_progress", "completed", "returned"):
                raise UserError(_("Only executed or returned tasks can be submitted."))
            rec._validate_completion_dependencies()
            rec.write({"state": "submitted", "completed_date": fields.Datetime.now()})

    def action_confirm(self):
        for rec in self:
            if rec.state != "submitted":
                raise UserError(_("Only submitted tasks can be confirmed."))
        self.write({"state": "confirmed", "completed_date": fields.Datetime.now()})

    def action_return(self):
        for rec in self:
            if rec.state != "submitted":
                raise UserError(_("Only submitted tasks can be returned."))
        self.write({"state": "returned"})

    def action_reset(self):
        self.write({"state": "pending", "completed_date": False})

    def _sync_profile_vals(self, vals, apply_default=False):
        profile_model = self.env["ftiq.task.profile"]
        profile = False
        if vals.get("task_profile_id"):
            profile = profile_model.browse(vals["task_profile_id"])
        elif vals.get("task_type"):
            profile = profile_model.get_default_profile(vals["task_type"])
            if profile:
                vals.setdefault("task_profile_id", profile.id)
        elif apply_default:
            profile = profile_model.get_default_profile("visit")
            if profile:
                vals.setdefault("task_profile_id", profile.id)
        if profile:
            vals["task_type"] = profile.code

    @staticmethod
    def _default_state_from_vals(vals):
        linked = any(vals.get(field_name) for field_name in (
            "plan_id", "plan_line_id", "visit_id", "sale_order_id",
            "payment_id", "stock_check_id", "project_task_id",
        ))
        return "pending" if linked else "draft"

    def _capture_location_from_context(self):
        ctx = self.env.context
        latitude = ctx.get("ftiq_latitude")
        longitude = ctx.get("ftiq_longitude")
        if not latitude or not longitude:
            return
        for rec in self:
            vals = {}
            if not rec.latitude:
                vals["latitude"] = latitude
            if not rec.longitude:
                vals["longitude"] = longitude
            if vals:
                rec.with_context(skip_assignment_notification=True, skip_project_task_sync=True).write(vals)

    @api.model
    def _find_attendance_for(self, user_id):
        if not user_id:
            return self.env["ftiq.field.attendance"]
        return self.env["ftiq.field.attendance"].get_active_attendance(user_id, fields.Date.context_today(self))

    def _ensure_execution_attendance(self):
        self.ensure_one()
        if not self.requires_check_in:
            return self._find_attendance_for(self.user_id.id)
        attendance = self.visit_id.attendance_id or self._find_attendance_for(self.user_id.id)
        if attendance:
            return attendance
        ctx = self.env.context
        return self.env["ftiq.field.attendance"].ensure_operation_attendance(
            self.user_id.id,
            attendance_date=fields.Date.context_today(self),
            latitude=self.latitude or ctx.get("ftiq_latitude"),
            longitude=self.longitude or ctx.get("ftiq_longitude"),
            accuracy=ctx.get("ftiq_accuracy", 0),
            is_mock=ctx.get("ftiq_is_mock", False),
            entry_reference=f"{self._name},{self.id}",
        )

    def _validate_profile_requirements_for_execution(self):
        self.ensure_one()
        if self.requires_partner and not self.partner_id:
            raise UserError(_("A client is required before starting this task."))
        if self.requires_associated_partner and not self.associated_partner_id:
            raise UserError(_("An associated client is required before starting this task."))
        if self.requires_user and not self.user_id:
            raise UserError(_("A representative is required before starting this task."))

    def _validate_completion_dependencies(self):
        self.ensure_one()
        self._validate_profile_requirements_for_execution()
        if self.requires_photos and self._count_execution_photos() < max(self.required_photo_count, 1):
            raise UserError(_("This task profile requires photo evidence before completion."))
        if self.requires_products and not self._has_product_evidence():
            raise UserError(_("This task profile requires product evidence before completion."))
        if self.task_type == "visit":
            allowed_states = ("submitted", "approved") if self.confirmation_required else ("approved",)
            if not self.visit_id or self.visit_id.state not in allowed_states:
                raise UserError(_("Visit tasks require a linked visit in the expected execution state."))
        elif self.task_type == "order":
            if not self.sale_order_id or self.sale_order_id.state not in ("sale", "done"):
                raise UserError(_("Order tasks can only be completed after the linked order is confirmed."))
        elif self.task_type == "collection":
            if not self.payment_id or self.payment_id.state not in ("in_process", "paid"):
                raise UserError(_("Collection tasks can only be completed after the linked collection is posted."))
        elif self.task_type == "stock":
            allowed_states = ("submitted", "reviewed") if self.confirmation_required else ("reviewed",)
            if not self.stock_check_id or self.stock_check_id.state not in allowed_states:
                raise UserError(_("Stock tasks require a linked stock check in the expected execution state."))
        elif not self.allow_manual_completion and not any((
            self.visit_id, self.sale_order_id, self.payment_id, self.stock_check_id, self.outcome,
        )):
            raise UserError(_("This task requires linked execution evidence before completion."))

    def _count_execution_photos(self):
        self.ensure_one()
        count = sum(1 for photo in (self.photo_1, self.photo_2, self.photo_3) if photo)
        if self.payment_id and self.payment_id.ftiq_receipt_image:
            count += 1
        if self.stock_check_id and self.stock_check_id.photo:
            count += 1
        if self.visit_id:
            count += sum(1 for photo in (self.visit_id.photo_1, self.visit_id.photo_2, self.visit_id.photo_3) if photo)
        return count

    def _has_product_evidence(self):
        self.ensure_one()
        return any((
            self.visit_id and self.visit_id.product_line_ids,
            self.sale_order_id and self.sale_order_id.order_line,
            self.stock_check_id and self.stock_check_id.line_ids,
        ))

    def _mark_linked_execution_in_progress(self):
        records = self.filtered(lambda rec: rec.state not in FTIQ_TASK_TERMINAL_STATES and rec.state != "submitted")
        if records:
            records.write({"state": "in_progress"})

    def _mark_linked_execution_submitted(self, completion_date=None):
        completion_date = completion_date or fields.Datetime.now()
        for rec in self.filtered(lambda task: task.state not in ("confirmed", "cancelled")):
            rec.write({
                "state": "submitted" if rec.confirmation_required else "completed",
                "completed_date": completion_date,
            })

    def _mark_linked_execution_confirmed(self, completion_date=None):
        completion_date = completion_date or fields.Datetime.now()
        for rec in self.filtered(lambda task: task.state != "cancelled"):
            rec.write({
                "state": "confirmed" if rec.confirmation_required else "completed",
                "completed_date": completion_date,
            })

    def _mark_linked_execution_returned(self):
        records = self.filtered(lambda rec: rec.confirmation_required and rec.state != "cancelled")
        if records:
            records.write({"state": "returned"})
