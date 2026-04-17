import base64
import json
import logging
import os

import requests

try:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
except ModuleNotFoundError:
    Request = None
    service_account = None

from odoo import models


_logger = logging.getLogger(__name__)


class FtiqFirebasePushService(models.AbstractModel):
    _name = "ftiq.firebase.push.service"
    _description = "FTIQ Firebase Push Service"

    _SCOPES = ("https://www.googleapis.com/auth/firebase.messaging",)
    _PLACEHOLDER_PREFIX = "REPLACE_WITH_"
    _RESERVED_DATA_KEYS = {"from", "message_type", "collapse_key"}
    _RESERVED_DATA_PREFIXES = ("google.", "gcm.", "gcm.notification.")

    def _is_placeholder(self, value):
        normalized = (value or "").strip()
        return not normalized or normalized.startswith(self._PLACEHOLDER_PREFIX)

    def _service_account_sources(self):
        parameters = self.env["ir.config_parameter"].sudo()
        return {
            "json": (parameters.get_param("ftiq.firebase_admin_sdk_json") or "").strip(),
            "json_base64": (
                parameters.get_param("ftiq.firebase_admin_sdk_json_base64") or ""
            ).strip(),
            "path": (parameters.get_param("ftiq.firebase_admin_sdk_path") or "").strip(),
            "env_json": (os.getenv("FTIQ_FIREBASE_ADMIN_SDK_JSON") or "").strip(),
            "env_json_base64": (
                os.getenv("FTIQ_FIREBASE_ADMIN_SDK_JSON_BASE64") or ""
            ).strip(),
            "env_path": (os.getenv("FTIQ_FIREBASE_ADMIN_SDK_PATH") or "").strip(),
        }

    def _service_account_payload(self):
        sources = self._service_account_sources()
        raw_json = sources["json"] or sources["env_json"]
        if not self._is_placeholder(raw_json):
            return raw_json

        encoded_json = sources["json_base64"] or sources["env_json_base64"]
        if not self._is_placeholder(encoded_json):
            try:
                return base64.b64decode(encoded_json).decode("utf-8")
            except Exception:
                _logger.exception(
                    "FTIQ Firebase push skipped: invalid base64 admin SDK payload",
                )
        return ""

    def _firebase_credentials(self):
        if Request is None or service_account is None:
            _logger.warning(
                "FTIQ Firebase push skipped: google-auth is not installed",
            )
            return None, ""
        sources = self._service_account_sources()
        json_payload = self._service_account_payload()
        if json_payload:
            try:
                credentials = service_account.Credentials.from_service_account_info(
                    json.loads(json_payload),
                    scopes=list(self._SCOPES),
                )
                return credentials, credentials.project_id or ""
            except Exception:
                _logger.exception(
                    "FTIQ Firebase push skipped: invalid admin SDK JSON payload",
                )
                return None, ""

        path = sources["path"] or sources["env_path"]
        if not self._is_placeholder(path):
            if not os.path.exists(path):
                _logger.warning(
                    "FTIQ Firebase push skipped: admin SDK path does not exist: %s",
                    path,
                )
                return None, ""
            credentials = service_account.Credentials.from_service_account_file(
                path,
                scopes=list(self._SCOPES),
            )
            return credentials, credentials.project_id or ""

        _logger.warning(
            "FTIQ Firebase push skipped: no Firebase admin SDK JSON/base64/path configured",
        )
        return None, ""

    def _firebase_access_token(self):
        credentials, project_id = self._firebase_credentials()
        if not credentials or not project_id:
            return "", ""
        credentials.refresh(Request())
        return credentials.token or "", project_id

    def _normalize_data_payload(self, data):
        normalized = {}
        for key, value in (data or {}).items():
            if value in (None, False):
                continue
            normalized_key = str(key or "").strip()
            if not normalized_key:
                continue
            lowered_key = normalized_key.lower()
            if (
                lowered_key in self._RESERVED_DATA_KEYS
                or lowered_key.startswith(self._RESERVED_DATA_PREFIXES)
            ):
                normalized_key = f"ftiq_{normalized_key.replace('.', '_')}"
            normalized[normalized_key] = str(value)
        return normalized

    def send_to_devices(self, devices, *, title, body, data=None, priority="normal"):
        active_devices = devices.filtered(
            lambda device: device.state == "active" and (device.push_token or "").strip()
        )
        if not active_devices:
            return {"sent": 0, "failed": 0, "invalidated": 0}

        access_token, project_id = self._firebase_access_token()
        if not access_token or not project_id:
            return {"sent": 0, "failed": len(active_devices), "invalidated": 0}

        url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        normalized_data = self._normalize_data_payload(data)
        invalid_devices = self.env["ftiq.mobile.device"]
        sent = 0
        failed = 0

        for device in active_devices:
            message_payload = {
                "message": {
                    "token": device.push_token.strip(),
                    "notification": {
                        "title": title,
                        "body": body,
                    },
                    "data": normalized_data,
                    "android": {
                        "priority": "HIGH" if priority == "urgent" else "NORMAL",
                        "notification": {
                            "channel_id": "ftiq_mobile_events",
                        },
                    },
                }
            }
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=message_payload,
                    timeout=20,
                )
            except Exception:
                failed += 1
                _logger.exception(
                    "FTIQ Firebase push request failed for device %s",
                    device.id,
                )
                continue

            if response.ok:
                sent += 1
                continue

            failed += 1
            response_text = response.text or ""
            if "UNREGISTERED" in response_text or "registration-token-not-registered" in response_text:
                invalid_devices |= device
                _logger.info(
                    "FTIQ Firebase push invalidated device %s token after provider rejection: status=%s",
                    device.id,
                    response.status_code,
                )
                continue
            _logger.warning(
                "FTIQ Firebase push rejected for device %s: status=%s body=%s",
                device.id,
                response.status_code,
                response_text[:1000],
            )

        if invalid_devices:
            invalid_devices.write({"push_token": False})

        return {
            "sent": sent,
            "failed": failed,
            "invalidated": len(invalid_devices),
        }

    def _message_deep_link(self, message):
        message.ensure_one()
        return f"ftiq://team-message?id={message.id}"

    def send_team_message_push(self, message):
        message.ensure_one()
        recipient_users = message._push_recipient_users()
        devices = self.env["ftiq.mobile.device"].search([
            ("company_id", "=", message.company_id.id),
            ("user_id", "in", recipient_users.ids),
            ("state", "=", "active"),
            ("push_token", "!=", False),
        ])
        return self.send_to_devices(
            devices,
            title=message.subject,
            body=message.body,
            priority=message.priority or "normal",
            data={
                "intent_json": json.dumps(
                    self.env["ftiq.mobile.notification"].build_target_intent(
                        target_model="ftiq.team.message",
                        target_res_id=message.id,
                    ),
                    ensure_ascii=False,
                ),
                "deep_link": self._message_deep_link(message),
                "message_id": message.id,
                "team_message_id": message.id,
                "notification_type": message.message_type or "",
                "target_model": "ftiq.team.message",
                "target_id": message.id,
                "task_id": message.task_id.id if message.task_id else "",
            },
        )
