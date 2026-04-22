from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


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
    ftiq_fsm_allowed_partner_ids = fields.Many2many(
        "res.partner",
        string="Allowed Field Service Customers",
        compute="_compute_ftiq_fsm_allowed_partner_ids",
    )
    ftiq_collection_payment_ids = fields.One2many(
        "account.payment",
        "ftiq_mobile_task_id",
        string="Collection Payments",
        copy=False,
    )
    ftiq_collection_payment_count = fields.Integer(
        string="Collection Payments",
        compute="_compute_ftiq_collection_payment_count",
    )

    def _ftiq_customer_domain(self, company=None):
        domain = [("customer_rank", ">", 0)]
        if company:
            domain += ["|", ("company_id", "=", False), ("company_id", "=", company.id)]
        return domain

    def _ftiq_allowed_partners_for_assignees(self, users, company=None):
        Partner = self.env["res.partner"]
        allowed_ids = set()

        real_user_ids = [
            user_id
            for user_id in users.ids
            if isinstance(user_id, int) and user_id > 0
        ]
        for user in self.env["res.users"].sudo().browse(real_user_ids).exists():
            partner_env = Partner.with_user(user).with_context(active_test=True)
            try:
                allowed_ids.update(partner_env.search(self._ftiq_customer_domain(company)).ids)
            except AccessError:
                continue
        if not allowed_ids:
            return Partner.browse()

        accessible_ids = Partner.search([("id", "in", list(allowed_ids))]).ids
        return Partner.browse(accessible_ids)

    @api.depends("company_id", "is_fsm", "user_ids")
    def _compute_ftiq_fsm_allowed_partner_ids(self):
        Partner = self.env["res.partner"]
        for task in self:
            company = task.company_id or self.env.company
            if task.is_fsm:
                task.ftiq_fsm_allowed_partner_ids = task._ftiq_allowed_partners_for_assignees(
                    task.user_ids,
                    company=company,
                )
            else:
                task.ftiq_fsm_allowed_partner_ids = Partner.search(
                    task._ftiq_customer_domain(company)
                )

    def _compute_ftiq_collection_payment_count(self):
        counts = {}
        if self.ids:
            rows = self.env["account.payment"].sudo().read_group(
                [("ftiq_mobile_task_id", "in", self.ids)],
                ["ftiq_mobile_task_id"],
                ["ftiq_mobile_task_id"],
            )
            counts = {
                row["ftiq_mobile_task_id"][0]: row["ftiq_mobile_task_id_count"]
                for row in rows
                if row.get("ftiq_mobile_task_id")
            }
        for task in self:
            task.ftiq_collection_payment_count = counts.get(task.id, 0)

    def action_ftiq_view_collection_payments(self):
        self.ensure_one()
        domain = [("ftiq_mobile_task_id", "=", self.id)]
        payments = self.env["account.payment"].search(domain)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Collection Payments"),
            "res_model": "account.payment",
            "view_mode": "list,form",
            "domain": domain,
            "context": {
                "default_ftiq_mobile_task_id": self.id,
                "default_partner_id": self.partner_id.id,
            },
        }
        if len(payments) == 1:
            action.update(
                {
                    "view_mode": "form",
                    "views": [(False, "form")],
                    "res_id": payments.id,
                }
            )
        return action

    def action_ftiq_create_subtask_assigned_to_me(self):
        """Upgrade compatibility for stale database views.

        The mobile subtask button was intentionally removed from the Odoo UI.
        Some databases still validate the previous inherited view during module
        upgrade before the new XML arch replaces it, so the method must exist.
        """
        return False

    @api.onchange("company_id", "project_id", "user_ids")
    def _onchange_ftiq_fsm_user_ids_partner_domain(self):
        if not self.is_fsm:
            return {}

        if not self.user_ids:
            self.partner_id = False
            partner_domain = [("id", "=", False)]
        else:
            allowed_partners = self.ftiq_fsm_allowed_partner_ids
            if self.partner_id and self.partner_id not in allowed_partners:
                self.partner_id = False
            partner_domain = [("id", "in", allowed_partners.ids)]

        return {"domain": {"partner_id": partner_domain}}

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
        tasks = super().create(vals_list)
        for task in tasks:
            task._ftiq_mobile_push_assignment(task.user_ids)
        return tasks

    def write(self, vals):
        previous_user_ids = {}
        if "user_ids" in vals:
            previous_user_ids = {task.id: set(task.user_ids.ids) for task in self}
        self._check_mobile_location_write(vals)
        result = super().write(vals)
        if previous_user_ids:
            for task in self:
                old_ids = previous_user_ids.get(task.id, set())
                new_users = task.user_ids.filtered(lambda user: user.id not in old_ids)
                task._ftiq_mobile_push_assignment(new_users)
        return result

    def _ftiq_mobile_task_type_label(self):
        self.ensure_one()
        task_type = self.ftiq_mobile_task_type or ""
        if not task_type:
            return _("Field Service")
        selection = dict(
            self._fields["ftiq_mobile_task_type"]._description_selection(self.env)
        )
        return selection.get(task_type, task_type)

    def _ftiq_mobile_push_assignment(self, users):
        if not users:
            return
        Device = self.env["ftiq.mobile.device"].sudo()
        for task in self:
            if not task.ftiq_mobile_task_type and not task.is_fsm:
                continue
            partners = users.mapped("partner_id").exists()
            if not partners:
                continue
            client_name = task.partner_id.display_name if task.partner_id else ""
            body_parts = [task.name or _("Task")]
            if client_name:
                body_parts.append(client_name)
            Device.push_to_partners(
                partners,
                _("New field service task assigned"),
                " - ".join(body_parts),
                data={
                    "notification_type": "task_assigned",
                    "target_model": "project.task",
                    "target_id": str(task.id),
                    "target_route": "task",
                    "related_client_id": str(task.partner_id.commercial_partner_id.id)
                    if task.partner_id
                    else "",
                    "task_type": task.ftiq_mobile_task_type or "",
                    "task_type_label": task._ftiq_mobile_task_type_label(),
                },
            )

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

    def _ftiq_mobile_stop_standard_timer(self, description=None, create_timesheet=True):
        self.ensure_one()
        if not self._ftiq_mobile_has_standard_timer():
            return False
        timer = self.user_timer_id
        if not timer or not timer.timer_start:
            return False

        if not create_timesheet:
            timer.unlink()
            return False

        timer_user = timer.user_id or self.env.user
        task = self.with_context(
            fsm_mode=bool("is_fsm" in self._fields and self.is_fsm),
            default_project_id=self.project_id.id,
        )
        result = task.action_timer_stop()
        if isinstance(result, dict) and result.get("res_model") == "project.task.create.timesheet":
            context = result.get("context") or {}
            time_spent = context.get("default_time_spent") or context.get("time_spent") or 0
            return self._ftiq_mobile_save_timer_timesheet(
                time_spent,
                description=description,
                context=context,
            )
        if isinstance(result, (int, float)) and result > 0:
            return self._ftiq_mobile_create_timer_timesheet(
                result,
                description=description,
                user=timer_user,
            )
        return False

    def _ftiq_mobile_save_timer_timesheet(self, time_spent, description=None, context=None):
        self.ensure_one()
        if not time_spent or not self.env.registry.get("project.task.create.timesheet"):
            if self.user_timer_id:
                self.user_timer_id.unlink()
            return False

        wizard = self.env["project.task.create.timesheet"].with_context(
            **(context or {})
        ).create(
            {
                "task_id": self.id,
                "time_spent": time_spent,
                "description": description or self.name or "/",
            }
        )
        return wizard.save_timesheet()

    def _ftiq_mobile_create_timer_timesheet(self, minutes_spent, description=None, user=None):
        self.ensure_one()
        if not self.env.registry.get("account.analytic.line") or not self.project_id:
            return minutes_spent

        minimum_duration = int(
            self.env["ir.config_parameter"].sudo().get_param(
                "timesheet_grid.timesheet_min_duration",
                0,
            )
        )
        rounding = int(
            self.env["ir.config_parameter"].sudo().get_param(
                "timesheet_grid.timesheet_rounding",
                0,
            )
        )
        time_spent = self._timer_rounding(minutes_spent, minimum_duration, rounding) / 60
        if not time_spent:
            return False

        values = {
            "task_id": self.id,
            "project_id": self.project_id.id,
            "date": fields.Date.context_today(self),
            "name": description or self.name or "/",
            "user_id": (user or self.env.user).id,
            "unit_amount": time_spent,
        }
        return self.env["account.analytic.line"].create(values)
