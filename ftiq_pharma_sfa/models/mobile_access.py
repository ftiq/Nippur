from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .mobile_access_catalog import (
    MOBILE_CATALOG_BY_FULL_KEY,
    MOBILE_PERMISSION_CATALOG,
    MOBILE_ROLE_SELECTION,
    MOBILE_SCOPE_SELECTION,
    mobile_full_key,
)
from .mobile_access_service import build_mobile_access_payload


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
                mobile_full_key(entry["scope"], entry["key"]) for entry in supported_entries
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
                full_key = mobile_full_key(entry["scope"], entry["key"])
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
                ("actions", "Actions"),
                ("global_features", "Global features"),
            ):
                scope_values = payload.get(scope_name, {})
                enabled_items = [key for key, value in scope_values.items() if value]
                if not enabled_items:
                    continue
                labels = []
                for key in enabled_items:
                    if scope_name == "navigation":
                        full_key = mobile_full_key("navigation", key)
                    elif scope_name == "workspaces":
                        full_key = mobile_full_key("workspace", key)
                    elif scope_name == "actions":
                        full_key = mobile_full_key("action", key)
                    elif scope_name == "global_features":
                        full_key = mobile_full_key("global_feature", key)
                    else:
                        full_key = mobile_full_key("section", key)
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
        return build_mobile_access_payload(self)
