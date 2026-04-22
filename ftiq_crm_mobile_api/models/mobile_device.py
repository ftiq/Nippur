import base64
import json
import logging

import requests

from odoo import api, fields, models

try:
    from google.auth.transport.requests import Request as GoogleAuthRequest
    from google.oauth2 import service_account
except ImportError:  # pragma: no cover - depends on server environment
    GoogleAuthRequest = None
    service_account = None


_logger = logging.getLogger(__name__)


class FtiqMobileDevice(models.Model):
    _name = "ftiq.mobile.device"
    _description = "FTIQ Mobile Device"
    _order = "last_seen_at desc, id desc"

    name = fields.Char(required=True, default="Mobile Device")
    installation_id = fields.Char(required=True, index=True)
    user_id = fields.Many2one("res.users", required=True, index=True, ondelete="cascade")
    partner_id = fields.Many2one(
        "res.partner",
        related="user_id.partner_id",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="user_id.company_id",
        store=True,
        readonly=True,
    )
    platform = fields.Char()
    device_name = fields.Char()
    device_model = fields.Char()
    app_version = fields.Char()
    build_number = fields.Char()
    locale = fields.Char()
    notification_enabled = fields.Boolean(default=False)
    location_enabled = fields.Boolean(default=False)
    fcm_token = fields.Char()
    last_seen_at = fields.Datetime(default=fields.Datetime.now)
    last_registration_at = fields.Datetime(default=fields.Datetime.now)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "ftiq_mobile_device_installation_unique",
            "unique(installation_id)",
            "The mobile installation identifier must be unique.",
        ),
    ]

    @api.model
    def _firebase_service_account_info(self):
        encoded = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("ftiq.firebase_admin_sdk_json_base64", "")
            .strip()
        )
        if not encoded:
            return None
        try:
            return json.loads(base64.b64decode(encoded).decode("utf-8"))
        except Exception:
            _logger.exception("Failed to decode Firebase admin SDK credentials")
            return None

    @api.model
    def _firebase_access_token(self):
        if service_account is None or GoogleAuthRequest is None:
            _logger.warning("Google auth libraries are not available for Firebase push")
            return None, None
        info = self._firebase_service_account_info()
        if not info:
            return None, None
        try:
            credentials = service_account.Credentials.from_service_account_info(
                info,
                scopes=["https://www.googleapis.com/auth/firebase.messaging"],
            )
            credentials.refresh(GoogleAuthRequest())
            return credentials.token, info.get("project_id")
        except Exception:
            _logger.exception("Failed to obtain Firebase access token")
            return None, None

    @api.model
    def _send_fcm_messages(self, tokens, title, body, data=None):
        tokens = [token.strip() for token in (tokens or []) if (token or "").strip()]
        if not tokens:
            _logger.info("FTIQ mobile push skipped: no FCM tokens title=%s", title or "")
            return 0
        access_token, project_id = self._firebase_access_token()
        if not access_token or not project_id:
            _logger.warning("FTIQ mobile push skipped: Firebase credentials unavailable")
            return 0

        endpoint = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        payload_data = {
            str(key): str(value)
            for key, value in (data or {}).items()
            if value not in (None, "")
        }
        sent = 0
        for token in sorted(set(tokens)):
            message = {
                "message": {
                    "token": token,
                    "notification": {
                        "title": title or "FTIQ",
                        "body": body or title or "",
                    },
                    "data": payload_data,
                    "android": {
                        "priority": "high",
                        "notification": {
                            "channel_id": "ftiq_mobile_alerts_v2",
                            "sound": "default",
                            "click_action": "FLUTTER_NOTIFICATION_CLICK",
                        },
                    },
                    "apns": {
                        "payload": {
                            "aps": {
                                "sound": "default",
                            }
                        }
                    },
                }
            }
            try:
                response = requests.post(
                    endpoint,
                    headers=headers,
                    json=message,
                    timeout=12,
                )
                if 200 <= response.status_code < 300:
                    sent += 1
                else:
                    _logger.warning(
                        "Firebase push failed for token %s: %s %s",
                        token[-8:],
                        response.status_code,
                        response.text,
                    )
            except Exception:
                _logger.exception("Unexpected Firebase push failure")
        _logger.info(
            "FTIQ mobile push sent=%s target_tokens=%s title=%s route=%s target_id=%s",
            sent,
            len(set(tokens)),
            title or "",
            payload_data.get("target_route", ""),
            payload_data.get("target_id", ""),
        )
        return sent

    @api.model
    def push_to_partners(self, partners, title, body, data=None):
        partner_ids = [partner.id for partner in partners.exists()]
        if not partner_ids:
            _logger.info("FTIQ mobile push skipped: no partner recipients title=%s", title or "")
            return 0
        devices = self.sudo().search(
            [
                ("partner_id", "in", partner_ids),
                ("active", "=", True),
                ("notification_enabled", "=", True),
                ("fcm_token", "!=", False),
            ]
        )
        tokens = [device.fcm_token for device in devices if device.fcm_token]
        if not tokens:
            _logger.info(
                "FTIQ mobile push skipped: no active FCM devices partners=%s title=%s",
                partner_ids,
                title or "",
            )
        return self._send_fcm_messages(tokens, title, body, data=data)
