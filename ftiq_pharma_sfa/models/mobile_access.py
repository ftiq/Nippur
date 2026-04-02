from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import ValidationError


MOBILE_ROLE_SELECTION = [
    ("representative", "Representative"),
    ("supervisor", "Supervisor"),
    ("manager", "Manager"),
]

MOBILE_SCOPE_SELECTION = [
    ("navigation", "Navigation"),
    ("workspace", "Workspace"),
    ("section", "Section"),
    ("action", "Action"),
    ("global_feature", "Global feature"),
]

MOBILE_PERMISSION_CATALOG = (
    {"scope": "navigation", "key": "dashboard", "label": "Dashboard tab", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 10},
    {"scope": "navigation", "key": "clients", "label": "Clients tab", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 20},
    {"scope": "navigation", "key": "visits", "label": "Visits tab", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 30},
    {"scope": "navigation", "key": "work", "label": "Work tab", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 40},
    {"scope": "navigation", "key": "more", "label": "More tab", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 50},
    {"scope": "workspace", "key": "attendance", "label": "Attendance workspace", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 110},
    {"scope": "workspace", "key": "finance", "label": "Finance workspace", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 120},
    {"scope": "workspace", "key": "team_hub", "label": "Team hub", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 130},
    {"scope": "workspace", "key": "operations_hub", "label": "Operations hub", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 140},
    {"scope": "workspace", "key": "notifications", "label": "Notifications center", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 150},
    {"scope": "workspace", "key": "device_sessions", "label": "Device sessions", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 160},
    {"scope": "section", "key": "dashboard.team", "label": "Dashboard team section", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 210},
    {"scope": "section", "key": "dashboard.area", "label": "Dashboard area section", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 220},
    {"scope": "section", "key": "dashboard.targets", "label": "Dashboard targets section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 230},
    {"scope": "section", "key": "client.profile", "label": "Client profile section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 240},
    {"scope": "section", "key": "client.finance", "label": "Client finance section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 250},
    {"scope": "section", "key": "visit.evidence", "label": "Visit evidence section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 260},
    {"scope": "section", "key": "visit.related_records", "label": "Visit related records section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 270},
    {"scope": "section", "key": "visit.thread", "label": "Visit thread section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 280},
    {"scope": "section", "key": "visit.activities", "label": "Visit activities section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 290},
    {"scope": "section", "key": "task.evidence", "label": "Task evidence section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 300},
    {"scope": "section", "key": "task.thread", "label": "Task thread section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 310},
    {"scope": "section", "key": "task.activities", "label": "Task activities section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 320},
    {"scope": "section", "key": "finance.notifications", "label": "Finance notifications section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 330},
    {"scope": "section", "key": "finance.schedules", "label": "Finance schedules section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 340},
    {"scope": "section", "key": "team.members", "label": "Team members section", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 350},
    {"scope": "section", "key": "team.messages", "label": "Team messages section", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 360},
    {"scope": "section", "key": "team.tasks", "label": "Team tasks section", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 370},
    {"scope": "section", "key": "thread.messages", "label": "Thread messages section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 380},
    {"scope": "section", "key": "thread.attachments", "label": "Thread attachments section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 390},
    {"scope": "section", "key": "thread.followers", "label": "Thread followers section", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 400},
    {"scope": "action", "key": "visit.edit", "label": "Edit visit", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 510},
    {"scope": "action", "key": "visit.start", "label": "Start visit", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 520},
    {"scope": "action", "key": "visit.end", "label": "End visit", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 530},
    {"scope": "action", "key": "visit.submit", "label": "Submit visit", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 540},
    {"scope": "action", "key": "visit.approve", "label": "Approve visit", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 550},
    {"scope": "action", "key": "visit.return", "label": "Return visit", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 560},
    {"scope": "action", "key": "visit.create_order", "label": "Create order from visit", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 570},
    {"scope": "action", "key": "visit.create_collection", "label": "Create collection from visit", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 580},
    {"scope": "action", "key": "visit.create_stock_check", "label": "Create stock check from visit", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 590},
    {"scope": "action", "key": "task.edit", "label": "Edit task", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 610},
    {"scope": "action", "key": "task.start", "label": "Start task", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 620},
    {"scope": "action", "key": "task.complete", "label": "Complete task", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 630},
    {"scope": "action", "key": "task.submit", "label": "Submit task", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 640},
    {"scope": "action", "key": "task.confirm", "label": "Confirm task", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 650},
    {"scope": "action", "key": "task.return", "label": "Return task", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 660},
    {"scope": "action", "key": "order.edit", "label": "Edit order", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 710},
    {"scope": "action", "key": "order.confirm", "label": "Confirm order", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 720},
    {"scope": "action", "key": "collection.edit", "label": "Edit collection", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 730},
    {"scope": "action", "key": "collection.collect", "label": "Collect payment", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 740},
    {"scope": "action", "key": "collection.deposit", "label": "Deposit collection", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 750},
    {"scope": "action", "key": "collection.verify", "label": "Verify collection", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 760},
    {"scope": "action", "key": "stock_check.edit", "label": "Edit stock check", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 770},
    {"scope": "action", "key": "stock_check.submit", "label": "Submit stock check", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 780},
    {"scope": "action", "key": "stock_check.review", "label": "Review stock check", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 790},
    {"scope": "action", "key": "stock_check.reset", "label": "Reset stock check", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 800},
    {"scope": "action", "key": "expense.edit", "label": "Edit expense", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 810},
    {"scope": "action", "key": "expense.submit", "label": "Submit expense", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 820},
    {"scope": "action", "key": "purchase.confirm", "label": "Confirm purchase", "supported_roles": ("manager",), "default_visibility": True, "ui_order": 830},
    {"scope": "action", "key": "purchase.approve", "label": "Approve purchase", "supported_roles": ("manager",), "default_visibility": True, "ui_order": 840},
    {"scope": "action", "key": "purchase.reject", "label": "Reject purchase", "supported_roles": ("manager",), "default_visibility": True, "ui_order": 850},
    {"scope": "action", "key": "team.publish_note", "label": "Publish team note", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 860},
    {"scope": "action", "key": "team.publish_alert", "label": "Publish team alert", "supported_roles": ("supervisor", "manager"), "default_visibility": True, "ui_order": 870},
    {"scope": "action", "key": "thread.post_message", "label": "Post thread message", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 880},
    {"scope": "action", "key": "thread.upload_attachment", "label": "Upload thread attachment", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 890},
    {"scope": "action", "key": "activity.mark_done", "label": "Complete activity", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 900},
    {"scope": "global_feature", "key": "location.attendance", "label": "Require location for attendance", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 1010},
    {"scope": "global_feature", "key": "location.visit_start", "label": "Require location for visit start", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 1020},
    {"scope": "global_feature", "key": "location.task_start", "label": "Require location for task start", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": True, "ui_order": 1030},
    {"scope": "global_feature", "key": "location.collection", "label": "Require location for collections", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": False, "ui_order": 1040},
    {"scope": "global_feature", "key": "location.order", "label": "Require location for orders", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": False, "ui_order": 1050},
    {"scope": "global_feature", "key": "location.stock_check", "label": "Require location for stock checks", "supported_roles": ("representative", "supervisor", "manager"), "default_visibility": False, "ui_order": 1060},
)

MOBILE_CATALOG_BY_FULL_KEY = {
    "%s.%s" % (entry["scope"], entry["key"]): entry for entry in MOBILE_PERMISSION_CATALOG
}


def _group_catalog_entries():
    grouped = defaultdict(list)
    for entry in MOBILE_PERMISSION_CATALOG:
        grouped[entry["scope"]].append(entry)
    return grouped


MOBILE_CATALOG_GROUPED = _group_catalog_entries()


class FtiqMobileAccessProfile(models.Model):
    _name = "ftiq.mobile.access.profile"
    _description = "FTIQ Mobile Access Profile"
    _order = "role, name, id"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)
    role = fields.Selection(MOBILE_ROLE_SELECTION, required=True, default="representative")
    description = fields.Text()
    permission_line_ids = fields.One2many(
        "ftiq.mobile.access.profile.permission",
        "profile_id",
        string="Permissions",
    )
    summary_html = fields.Html(
        string="Enabled permissions summary",
        compute="_compute_summary_html",
        sanitize=False,
    )

    _sql_constraints = [
        ("ftiq_mobile_access_profile_code_uniq", "unique(code)", "The mobile access profile code must be unique."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_permission_lines(reset_to_defaults=True)
        return records

    def write(self, vals):
        role_changed = "role" in vals
        result = super().write(vals)
        if role_changed:
            self._sync_permission_lines(reset_to_defaults=True)
        else:
            self._sync_permission_lines(reset_to_defaults=False)
        return result

    def action_sync_permission_catalog(self):
        self._sync_permission_lines(reset_to_defaults=False)
        return True

    def _sync_permission_lines(self, reset_to_defaults=False):
        line_model = self.env["ftiq.mobile.access.profile.permission"]
        for profile in self:
            supported_entries = [
                entry for entry in MOBILE_PERMISSION_CATALOG if profile.role in entry["supported_roles"]
            ]
            supported_full_keys = {
                "%s.%s" % (entry["scope"], entry["key"]) for entry in supported_entries
            }
            if reset_to_defaults:
                profile.permission_line_ids.unlink()
                existing_by_key = {}
            else:
                obsolete_lines = profile.permission_line_ids.filtered(
                    lambda line: line.full_key not in supported_full_keys
                )
                if obsolete_lines:
                    obsolete_lines.unlink()
                existing_by_key = {
                    line.full_key: line for line in profile.permission_line_ids
                }
            create_values = []
            for entry in supported_entries:
                full_key = "%s.%s" % (entry["scope"], entry["key"])
                values = {
                    "scope": entry["scope"],
                    "permission_key": entry["key"],
                    "full_key": full_key,
                    "label": entry["label"],
                    "enabled": bool(entry["default_visibility"]),
                    "default_visibility": bool(entry["default_visibility"]),
                    "ui_order": entry["ui_order"],
                    "supported_roles": ", ".join(entry["supported_roles"]),
                }
                existing = existing_by_key.get(full_key)
                if existing:
                    metadata_values = {
                        key: value
                        for key, value in values.items()
                        if key != "enabled" and existing[key] != value
                    }
                    if metadata_values:
                        existing.write(metadata_values)
                else:
                    create_values.append({
                        **values,
                        "profile_id": profile.id,
                    })
            if create_values:
                line_model.create(create_values)

    @api.depends(
        "permission_line_ids.enabled",
        "permission_line_ids.scope",
        "permission_line_ids.label",
        "permission_line_ids.ui_order",
    )
    def _compute_summary_html(self):
        for profile in self:
            enabled_lines = profile.permission_line_ids.filtered("enabled").sorted(
                key=lambda line: (line.scope, line.ui_order, line.id)
            )
            if not enabled_lines:
                profile.summary_html = "<p>No permissions enabled.</p>"
                continue
            grouped = defaultdict(list)
            for line in enabled_lines:
                grouped[line.scope].append(line.label)
            parts = []
            for scope_value, scope_label in MOBILE_SCOPE_SELECTION:
                labels = grouped.get(scope_value, [])
                if not labels:
                    continue
                items = "".join("<li>%s</li>" % label for label in labels)
                parts.append("<p><strong>%s</strong></p><ul>%s</ul>" % (scope_label, items))
            profile.summary_html = "".join(parts)

    def permission_map(self):
        self.ensure_one()
        return {
            line.full_key: bool(line.enabled)
            for line in self.permission_line_ids
        }


class FtiqMobileAccessProfilePermission(models.Model):
    _name = "ftiq.mobile.access.profile.permission"
    _description = "FTIQ Mobile Access Profile Permission"
    _order = "scope, ui_order, id"

    profile_id = fields.Many2one(
        "ftiq.mobile.access.profile",
        required=True,
        ondelete="cascade",
    )
    scope = fields.Selection(MOBILE_SCOPE_SELECTION, required=True)
    permission_key = fields.Char(required=True)
    full_key = fields.Char(required=True)
    label = fields.Char(required=True)
    enabled = fields.Boolean(default=True)
    default_visibility = fields.Boolean(default=True)
    ui_order = fields.Integer(default=0)
    supported_roles = fields.Char(readonly=True)

    _sql_constraints = [
        (
            "ftiq_mobile_access_profile_permission_uniq",
            "unique(profile_id, full_key)",
            "Each mobile permission can only exist once per profile.",
        ),
    ]


class ResUsersMobileAccess(models.Model):
    _inherit = "res.users"

    ftiq_mobile_access_enabled = fields.Boolean(
        string="Mobile access enabled",
        default=True,
    )
    ftiq_mobile_access_profile_id = fields.Many2one(
        "ftiq.mobile.access.profile",
        string="Mobile access profile",
        ondelete="restrict",
    )
    ftiq_mobile_role = fields.Selection(
        MOBILE_ROLE_SELECTION,
        string="Mobile role",
        compute="_compute_ftiq_mobile_role",
    )
    ftiq_mobile_access_issue = fields.Char(
        string="Mobile access issue",
        compute="_compute_ftiq_mobile_access_summary",
    )
    ftiq_mobile_access_summary = fields.Html(
        string="Effective mobile permissions",
        compute="_compute_ftiq_mobile_access_summary",
        sanitize=False,
    )

    @api.depends("groups_id")
    def _compute_ftiq_mobile_role(self):
        for user in self:
            user.ftiq_mobile_role = user._ftiq_mobile_role_value() or False

    @api.depends(
        "groups_id",
        "ftiq_mobile_access_enabled",
        "ftiq_mobile_access_profile_id",
        "ftiq_mobile_access_profile_id.permission_line_ids.enabled",
    )
    def _compute_ftiq_mobile_access_summary(self):
        for user in self:
            payload = user.get_ftiq_mobile_access_payload()
            issue = payload.get("reason") or ""
            user.ftiq_mobile_access_issue = issue.replace("_", " ").strip().title()
            if not payload.get("enabled"):
                reason = issue or "mobile_access_disabled"
                user.ftiq_mobile_access_summary = "<p><strong>%s</strong></p>" % reason.replace("_", " ").strip().title()
                continue
            grouped = []
            for scope_name, scope_label in (
                ("navigation", "Navigation"),
                ("workspaces", "Workspaces"),
                ("sections", "Sections"),
                ("global_features", "Global features"),
            ):
                scope_values = payload.get(scope_name, {})
                enabled_items = [key for key, value in scope_values.items() if value]
                if not enabled_items:
                    continue
                labels = []
                for key in enabled_items:
                    if scope_name == "navigation":
                        full_key = "navigation.%s" % key
                    elif scope_name == "workspaces":
                        full_key = "workspace.%s" % key
                    elif scope_name == "global_features":
                        full_key = "global_feature.%s" % key
                    else:
                        full_key = "section.%s" % key
                    entry = MOBILE_CATALOG_BY_FULL_KEY.get(full_key)
                    labels.append(entry["label"] if entry else key)
                items = "".join("<li>%s</li>" % label for label in labels)
                grouped.append("<p><strong>%s</strong></p><ul>%s</ul>" % (scope_label, items))
            user.ftiq_mobile_access_summary = "".join(grouped) or "<p>No permissions enabled.</p>"

    @api.constrains("ftiq_mobile_access_profile_id", "groups_id")
    def _check_mobile_access_profile_role(self):
        for user in self:
            profile = user.ftiq_mobile_access_profile_id
            role = user._ftiq_mobile_role_value()
            if profile and role and profile.role != role:
                raise ValidationError("The selected mobile access profile does not match the user's FTIQ role.")

    def _ftiq_mobile_role_value(self):
        self.ensure_one()
        if self.has_group("ftiq_pharma_sfa.group_ftiq_manager"):
            return "manager"
        if self.has_group("ftiq_pharma_sfa.group_ftiq_supervisor"):
            return "supervisor"
        if self.has_group("ftiq_pharma_sfa.group_ftiq_rep"):
            return "representative"
        return ""

    def get_ftiq_mobile_access_payload(self):
        self.ensure_one()
        role = self._ftiq_mobile_role_value()
        payload = {
            "enabled": False,
            "role": role,
            "profile": {},
            "navigation": {
                entry["key"]: False
                for entry in MOBILE_CATALOG_GROUPED["navigation"]
            },
            "workspaces": {
                entry["key"]: False
                for entry in MOBILE_CATALOG_GROUPED["workspace"]
            },
            "sections": {
                entry["key"]: False
                for entry in MOBILE_CATALOG_GROUPED["section"]
            },
            "actions": {
                entry["key"]: False
                for entry in MOBILE_CATALOG_GROUPED["action"]
            },
            "global_features": {
                entry["key"]: False
                for entry in MOBILE_CATALOG_GROUPED["global_feature"]
            },
            "reason": "",
        }
        if not role:
            payload["reason"] = "missing_ftiq_role"
            return payload
        if not self.ftiq_mobile_access_enabled:
            payload["reason"] = "mobile_access_disabled"
            return payload
        profile = self.ftiq_mobile_access_profile_id
        if not profile:
            payload["reason"] = "missing_mobile_profile"
            return payload
        if profile.role != role:
            payload["reason"] = "profile_role_mismatch"
            return payload

        permission_map = profile.permission_map()
        payload["enabled"] = True
        payload["profile"] = {
            "id": profile.id,
            "name": profile.name,
            "code": profile.code,
        }
        payload["reason"] = ""
        for entry in MOBILE_PERMISSION_CATALOG:
            if role not in entry["supported_roles"]:
                continue
            scope_name = entry["scope"]
            key_name = entry["key"]
            full_key = "%s.%s" % (scope_name, key_name)
            value = bool(permission_map.get(full_key))
            if scope_name == "workspace":
                payload["workspaces"][key_name] = value
            elif scope_name == "navigation":
                payload["navigation"][key_name] = value
            elif scope_name == "action":
                payload["actions"][key_name] = value
            elif scope_name == "global_feature":
                payload["global_features"][key_name] = value
            else:
                payload["sections"][key_name] = value
        return payload
