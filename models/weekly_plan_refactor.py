from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FtiqWeeklyPlan(models.Model):
    _inherit = "ftiq.weekly.plan"

    task_profile_id = fields.Many2one(
        "ftiq.task.profile",
        string="Task Profile",
        tracking=True,
        default=lambda self: self.env["ftiq.task.profile"].get_default_profile("visit"),
    )
    task_generation_policy = fields.Selection(
        [
            ("create", "On Plan Creation"),
            ("approve", "On Approval"),
            ("manual", "Manual Sync"),
        ],
        string="Task Generation Policy",
        default="approve",
        required=True,
        tracking=True,
    )

    def write(self, vals):
        result = super().write(vals)
        if any(key in vals for key in ("task_profile_id", "task_generation_policy")):
            self._sync_project_and_tasks(create_project=False, create_daily_tasks=False)
        return result

    def action_submit(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft plans can be submitted."))
            rec._validate_plan_setup()
            rec.state = "submitted"
        create_now = self.filtered(lambda rec: rec.task_generation_policy == "create")
        defer = self - create_now
        if create_now:
            create_now._sync_project_and_tasks(create_project=True, create_daily_tasks=True)
        if defer:
            defer._sync_project_and_tasks(create_project=True, create_daily_tasks=False)

    def action_approve(self):
        for rec in self:
            if rec.state != "submitted":
                raise UserError(_("Only submitted plans can be approved."))
            rec._validate_plan_setup()
            rec.state = "approved"
        create_now = self.filtered(lambda rec: rec.task_generation_policy in ("create", "approve"))
        defer = self - create_now
        if create_now:
            create_now._sync_project_and_tasks(create_project=True, create_daily_tasks=True)
        if defer:
            defer._sync_project_and_tasks(create_project=True, create_daily_tasks=False)

    def action_sync_project(self):
        self._validate_plan_setup()
        self._sync_project_and_tasks(create_project=True, create_daily_tasks=True)

    def _sync_project_and_tasks(self, create_project=True, create_daily_tasks=True):
        Project = self.env["project.project"].with_context(mail_create_nosubscribe=True, tracking_disable=True)
        Task = self.env["project.task"].with_context(mail_create_nosubscribe=True, tracking_disable=True)
        DailyTask = self.env["ftiq.daily.task"].with_context(
            skip_assignment_notification=True,
            skip_project_task_sync=True,
            mail_create_nosubscribe=True,
            tracking_disable=True,
        )
        default_profile = self.env["ftiq.task.profile"].get_default_profile("visit")
        for rec in self:
            project = rec.project_id
            project_name = rec._build_project_display_name()
            if not project and create_project:
                project = Project.create({
                    "name": project_name,
                    "user_id": rec.supervisor_id.id or self.env.uid,
                    "company_id": self.env.company.id,
                })
                rec.project_id = project
            elif project:
                project.with_context(tracking_disable=True).write({
                    "name": project_name,
                    "user_id": rec.supervisor_id.id or self.env.uid,
                })

            project_task_map = {}
            for line in rec.line_ids:
                assigned_user = line.user_id or rec.user_id
                task_vals = {
                    "name": _("%s - %s") % (line.partner_id.display_name, rec.name),
                    "partner_id": line.partner_id.id,
                    "date_deadline": self._line_deadline_datetime(line),
                    "planned_date_begin": self._line_datetime(line),
                    "description": line.note or rec.note or False,
                    "user_ids": [(6, 0, [assigned_user.id])] if assigned_user else False,
                    "ftiq_plan_id": rec.id,
                    "ftiq_plan_line_id": line.id,
                    "project_id": project.id if project else False,
                }
                if line.project_task_id and line.project_task_id.exists():
                    line.project_task_id.with_context(tracking_disable=True).write(task_vals)
                    project_task_map[line.id] = line.project_task_id
                elif project:
                    line.project_task_id = Task.create(task_vals)
                    project_task_map[line.id] = line.project_task_id

            if not create_daily_tasks:
                continue

            task_profile = rec.task_profile_id or default_profile
            for line in rec.line_ids:
                assigned_user = line.user_id or rec.user_id
                project_task = project_task_map.get(line.id)
                daily_vals = {
                    "task_profile_id": task_profile.id if task_profile else False,
                    "task_type": task_profile.code if task_profile else "visit",
                    "partner_id": line.partner_id.id,
                    "associated_partner_id": line.partner_id.id,
                    "user_id": assigned_user.id if assigned_user else False,
                    "scheduled_date": self._line_datetime(line),
                    "priority": "1",
                    "description": line.note or rec.note or False,
                    "plan_id": rec.id,
                    "plan_line_id": line.id,
                    "project_id": project.id if project else False,
                    "project_task_id": project_task.id if project_task else False,
                    "state": "pending",
                }
                if line.daily_task_id and line.daily_task_id.exists():
                    line.daily_task_id.with_context(
                        skip_assignment_notification=True,
                        skip_project_task_sync=True,
                        tracking_disable=True,
                    ).write(daily_vals)
                    continue
                line.daily_task_id = DailyTask.create(daily_vals)


class FtiqWeeklyPlanLine(models.Model):
    _inherit = "ftiq.weekly.plan.line"

    execution_state = fields.Selection(
        [
            ("not_ready", "Not Ready"),
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("confirmed", "Confirmed"),
            ("returned", "Returned"),
            ("completed", "Completed"),
            ("missed", "Missed"),
        ],
        compute="_compute_execution_state",
    )
    execution_reference = fields.Char(compute="_compute_execution_state")

    @api.depends("state", "visit_id.state", "daily_task_id.state")
    def _compute_execution_state(self):
        for rec in self:
            execution_state = "not_ready"
            execution_reference = ""
            if rec.visit_id:
                execution_state = rec.visit_id.state
                execution_reference = rec.visit_id.display_name
            elif rec.daily_task_id:
                execution_state = rec.daily_task_id.state
                execution_reference = rec.daily_task_id.display_name
            elif rec.state == "missed":
                execution_state = "missed"
            elif rec.state == "completed":
                execution_state = "completed"
            elif rec.state == "pending":
                execution_state = "pending"
            rec.execution_state = execution_state
            rec.execution_reference = execution_reference
