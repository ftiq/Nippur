from odoo import _, fields, models
from odoo.exceptions import ValidationError


class FtiqPlanWizard(models.TransientModel):
    _inherit = "ftiq.plan.wizard"

    task_profile_id = fields.Many2one(
        "ftiq.task.profile",
        string="Task Profile",
        default=lambda self: self.env["ftiq.task.profile"].get_default_profile("visit"),
    )

    def _create_plan(self):
        if not self.team_id:
            raise ValidationError(_("Select a sales team before creating the plan."))
        if not self.partner_ids:
            raise ValidationError(_("Select at least one client before creating the plan."))
        plan_model = self.env["ftiq.weekly.plan"]
        schedule_date = self.schedule_date or fields.Date.today()
        plan_name = plan_model._build_plan_display_name(self.team_id, schedule_date, self.plan_name)
        plan = plan_model.with_context(skip_assignment_notification=True).create({
            "name": plan_name,
            "team_id": self.team_id.id,
            "task_type_id": self.task_type_id.id if self.task_type_id else False,
            "task_profile_id": self.task_profile_id.id if self.task_profile_id else False,
            "task_generation_policy": self.task_generation_policy,
            "week_start": schedule_date,
            "note": self.note,
        })
        self.env["ftiq.weekly.plan.line"].create([{
            "plan_id": plan.id,
            "user_id": self.user_id.id if self.user_id else False,
            "partner_id": partner.id,
            "scheduled_date": schedule_date,
        } for partner in self.partner_ids])
        plan._notify_assignment()
        plan._sync_project_and_tasks(
            create_project=True,
            create_daily_tasks=plan.task_generation_policy == "create",
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "ftiq.weekly.plan",
            "res_id": plan.id,
            "view_mode": "form",
            "target": "current",
        }
