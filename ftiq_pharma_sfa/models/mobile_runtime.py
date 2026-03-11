import json
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


_VERSION_SEGMENT_PATTERN = re.compile(r"\d+")


def _version_key(value):
    if not value:
        return ()
    return tuple(int(segment) for segment in _VERSION_SEGMENT_PATTERN.findall(str(value)))


def _compare_versions(left, right):
    left_key = list(_version_key(left))
    right_key = list(_version_key(right))
    max_length = max(len(left_key), len(right_key))
    left_key.extend([0] * (max_length - len(left_key)))
    right_key.extend([0] * (max_length - len(right_key)))
    if left_key < right_key:
        return -1
    if left_key > right_key:
        return 1
    return 0


class FtiqMobileRuntimePolicy(models.Model):
    _name = "ftiq.mobile.runtime.policy"
    _description = "Mobile Runtime Policy"
    _order = "company_id"
    _rec_name = "name"

    name = fields.Char(compute="_compute_name", store=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
        index=True,
    )
    active = fields.Boolean(default=True)
    registration_required = fields.Boolean(
        string="Registration Required",
        default=True,
        help="When enabled, every authenticated mobile installation must be registered in the device registry.",
    )
    maintenance_enabled = fields.Boolean(default=False)
    maintenance_message = fields.Text(translate=True)
    android_min_version = fields.Char()
    android_recommended_version = fields.Char()
    android_latest_version = fields.Char()
    android_store_url = fields.Char()
    android_force_update = fields.Boolean(default=True)
    ios_min_version = fields.Char()
    ios_recommended_version = fields.Char()
    ios_latest_version = fields.Char()
    ios_store_url = fields.Char()
    ios_force_update = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "ftiq_mobile_runtime_policy_company_unique",
            "unique(company_id)",
            "Only one mobile runtime policy is allowed per company.",
        ),
    ]

    @api.depends("company_id")
    def _compute_name(self):
        for rec in self:
            company_name = rec.company_id.display_name or _("Company")
            rec.name = _("%s Mobile Runtime") % company_name

    def _platform_values(self, platform):
        self.ensure_one()
        normalized_platform = (platform or "").strip().lower()
        if normalized_platform == "ios":
            return {
                "platform": "ios",
                "min_version": self.ios_min_version or "",
                "recommended_version": self.ios_recommended_version or "",
                "latest_version": self.ios_latest_version or "",
                "store_url": self.ios_store_url or "",
                "force_update": bool(self.ios_force_update),
            }
        return {
            "platform": "android",
            "min_version": self.android_min_version or "",
            "recommended_version": self.android_recommended_version or "",
            "latest_version": self.android_latest_version or "",
            "store_url": self.android_store_url or "",
            "force_update": bool(self.android_force_update),
        }

    def evaluate_client(self, platform="", app_version="", build_number="", device=False):
        self.ensure_one()
        values = self._platform_values(platform)
        min_version = values["min_version"]
        recommended_version = values["recommended_version"]
        latest_version = values["latest_version"]
        current_version = (app_version or "").strip()
        update_required = bool(
            current_version
            and min_version
            and values["force_update"]
            and _compare_versions(current_version, min_version) < 0
        )
        update_available = False
        if current_version and latest_version and _compare_versions(current_version, latest_version) < 0:
            update_available = True
        elif current_version and recommended_version and _compare_versions(current_version, recommended_version) < 0:
            update_available = True

        reason = "ok"
        message = ""
        allowed = True
        if self.maintenance_enabled:
            reason = "maintenance"
            message = self.maintenance_message or _("The mobile application is temporarily under maintenance.")
            allowed = False
        elif device and device.state == "revoked":
            reason = "device_revoked"
            message = _("This device has been revoked. Contact your administrator.")
            allowed = False
        elif update_required:
            reason = "update_required"
            message = _("A newer app version is required before you can continue.")
            allowed = False

        return {
            "policy_id": self.id,
            "platform": values["platform"],
            "current_version": current_version,
            "build_number": (build_number or "").strip(),
            "min_version": min_version,
            "recommended_version": recommended_version,
            "latest_version": latest_version,
            "store_url": values["store_url"],
            "force_update": values["force_update"],
            "registration_required": bool(self.registration_required),
            "maintenance_enabled": bool(self.maintenance_enabled),
            "maintenance_message": self.maintenance_message or "",
            "update_available": update_available,
            "update_required": update_required,
            "allowed": allowed,
            "reason": reason,
            "message": message,
            "device_registered": bool(device),
            "device_state": device.state if device else "unregistered",
        }


class FtiqMobileDevice(models.Model):
    _name = "ftiq.mobile.device"
    _description = "Mobile Device"
    _order = "last_seen_at desc, id desc"
    _rec_name = "name"

    name = fields.Char(compute="_compute_name", store=True)
    user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one("res.company", related="user_id.company_id", store=True, index=True)
    team_id = fields.Many2one("crm.team", related="user_id.sale_team_id", store=True)
    installation_id = fields.Char(required=True, copy=False, index=True)
    platform = fields.Selection(
        [
            ("android", "Android"),
            ("ios", "iOS"),
            ("web", "Web"),
            ("windows", "Windows"),
            ("macos", "macOS"),
            ("linux", "Linux"),
            ("unknown", "Unknown"),
        ],
        default="unknown",
        required=True,
        index=True,
    )
    state = fields.Selection(
        [("active", "Active"), ("revoked", "Revoked")],
        default="active",
        required=True,
        tracking=True,
        index=True,
    )
    app_version = fields.Char()
    build_number = fields.Char()
    locale_code = fields.Char()
    device_name = fields.Char()
    device_model = fields.Char()
    device_brand = fields.Char()
    device_manufacturer = fields.Char()
    os_version = fields.Char()
    notification_permission = fields.Boolean()
    location_permission = fields.Char()
    location_services_enabled = fields.Boolean()
    biometrics_available = fields.Boolean()
    push_token = fields.Char(copy=False)
    capabilities_json = fields.Text()
    last_seen_at = fields.Datetime(default=fields.Datetime.now, index=True)
    last_login_at = fields.Datetime()
    last_ip = fields.Char()
    last_user_agent = fields.Char()

    _sql_constraints = [
        (
            "ftiq_mobile_device_installation_user_unique",
            "unique(user_id, installation_id)",
            "The same installation can only be registered once per user.",
        ),
    ]

    @api.depends("device_name", "device_model", "platform", "user_id")
    def _compute_name(self):
        for rec in self:
            label = rec.device_name or rec.device_model or rec.platform or _("Device")
            if rec.user_id:
                rec.name = _("%s - %s") % (rec.user_id.display_name, label)
            else:
                rec.name = label

    @api.constrains("installation_id")
    def _check_installation_id(self):
        for rec in self:
            if not (rec.installation_id or "").strip():
                raise ValidationError(_("Installation ID is required."))

    def action_activate(self):
        self.write({"state": "active"})

    def action_revoke(self):
        self.write({"state": "revoked"})

    @api.model
    def register_current(self, payload, remote_ip="", user_agent=""):
        installation_id = (payload.get("installation_id") or "").strip()
        if not installation_id:
            raise ValidationError(_("installation_id is required."))

        user = self.env.user
        device = self.search(
            [("user_id", "=", user.id), ("installation_id", "=", installation_id)],
            limit=1,
        )

        capabilities = payload.get("capabilities")
        capabilities_json = ""
        if capabilities not in (None, "", False):
            capabilities_json = json.dumps(capabilities, ensure_ascii=False, sort_keys=True)

        values = {
            "user_id": user.id,
            "installation_id": installation_id,
            "platform": (payload.get("platform") or "unknown").strip().lower() or "unknown",
            "app_version": (payload.get("app_version") or "").strip(),
            "build_number": (payload.get("build_number") or "").strip(),
            "locale_code": (payload.get("locale_code") or "").strip(),
            "device_name": (payload.get("device_name") or "").strip(),
            "device_model": (payload.get("device_model") or "").strip(),
            "device_brand": (payload.get("device_brand") or "").strip(),
            "device_manufacturer": (payload.get("device_manufacturer") or "").strip(),
            "os_version": (payload.get("os_version") or "").strip(),
            "notification_permission": bool(payload.get("notification_permission")),
            "location_permission": (payload.get("location_permission") or "").strip(),
            "location_services_enabled": bool(payload.get("location_services_enabled")),
            "biometrics_available": bool(payload.get("biometrics_available")),
            "push_token": (payload.get("push_token") or "").strip(),
            "capabilities_json": capabilities_json,
            "last_seen_at": fields.Datetime.now(),
            "last_ip": (remote_ip or "")[:128],
            "last_user_agent": (user_agent or "")[:512],
        }
        if payload.get("mark_logged_in"):
            values["last_login_at"] = fields.Datetime.now()

        if device:
            if device.state == "revoked":
                values = {
                    "last_seen_at": values["last_seen_at"],
                    "last_login_at": values.get("last_login_at") or device.last_login_at,
                    "last_ip": values["last_ip"],
                    "last_user_agent": values["last_user_agent"],
                }
            device.write(values)
        else:
            device = self.create(values)
        return device
