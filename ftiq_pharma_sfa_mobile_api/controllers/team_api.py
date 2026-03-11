from odoo import _, http
from odoo.exceptions import AccessError
from odoo.http import request

from odoo.addons.ftiq_pharma_sfa.controllers.dashboard import FtiqDashboardController

from .base_api import FtiqMobileApiBase


class FtiqMobileTeamApi(FtiqMobileApiBase):
    @http.route("/ftiq_mobile_api/v1/team-hub", type="http", auth="user", methods=["GET"], csrf=False)
    def team_hub(self, **kwargs):
        return self._dispatch(self._team_hub)

    @http.route("/ftiq_mobile_api/v1/team-hub/messages", type="http", auth="user", methods=["POST"], csrf=False)
    def team_hub_message_create(self, **kwargs):
        return self._dispatch(self._team_hub_message_create)

    def _team_hub(self):
        role, teams, scope_users = self._scope_users()
        if role not in {"supervisor", "manager"}:
            raise AccessError(_("You do not have permission to open the team hub."))

        current_user = self._current_user()
        dashboard_data = FtiqDashboardController().get_dashboard_data()
        team_rows = {
            row.get("user_id"): row
            for row in dashboard_data.get("team_rows", [])
            if row.get("user_id")
        }
        member_users = scope_users.filtered(lambda user: user.id != current_user.id)
        active_states = ("draft", "pending", "in_progress", "submitted", "returned")
        tasks = request.env["ftiq.daily.task"].search(
            [
                ("user_id", "in", member_users.ids),
                ("state", "in", active_states),
            ],
            order="scheduled_date asc, priority desc, id desc",
            limit=40,
        )
        messages = self._search_scoped(
            "ftiq.team.message",
            order="create_date desc, id desc",
            limit=40,
        )
        members = []
        for member in member_users:
            metrics = team_rows.get(member.id, {})
            members.append(
                {
                    **self._serialize_user(member),
                    "checked_in": bool(metrics.get("checked_in")),
                    "planned": metrics.get("planned", 0),
                    "completed": metrics.get("completed", 0),
                    "approved_visits": metrics.get("approved_visits", 0),
                    "orders_amount": metrics.get("orders_amount", 0.0),
                    "collections_amount": metrics.get("collections_amount", 0.0),
                    "overdue_tasks": metrics.get("overdue_tasks", 0),
                    "compliance": metrics.get("compliance", 0.0),
                }
            )

        return self._ok(
            {
                "role": role,
                "current_user": self._serialize_user(current_user),
                "teams": [
                    {
                        "id": team.id,
                        "name": team.display_name,
                    }
                    for team in teams
                ],
                "members": members,
                "tasks": [self._serialize_task(task) for task in tasks],
                "messages": [self._serialize_team_message(message) for message in messages],
            }
        )

    def _team_hub_message_create(self):
        self._ensure_role({"supervisor", "manager"}, "publish team messages")
        payload = self._json_body()
        message = request.env["ftiq.team.message"].create(
            {
                "subject": (payload.get("subject") or "").strip(),
                "body": (payload.get("body") or "").strip(),
                "message_type": (payload.get("message_type") or "note").strip() or "note",
                "priority": (payload.get("priority") or "normal").strip() or "normal",
                "team_id": payload.get("team_id"),
                "target_user_id": payload.get("target_user_id") or False,
                "task_id": payload.get("task_id") or False,
                "is_team_wide": self._payload_bool(payload, "is_team_wide", not bool(payload.get("target_user_id"))),
            }
        )
        return self._ok(self._serialize_team_message(message), status=201)
