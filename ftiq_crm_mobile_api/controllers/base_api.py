import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import date, datetime

from odoo import _, fields, http
from odoo.exceptions import (
    AccessDenied,
    AccessError,
    RedirectWarning,
    UserError,
    ValidationError,
)
from odoo.http import request
from odoo.osv import expression
from odoo.tools import html2plaintext


_logger = logging.getLogger(__name__)


class FtiqCrmApiBase(http.Controller):
    """Shared helpers for the Django-compatible CRM mobile API."""

    _TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7

    def _dispatch(self, callback):
        try:
            self._apply_request_lang()
            return callback()
        except AccessDenied as exc:
            return self._error(str(exc) or _("Authentication required."), status=401)
        except AccessError as exc:
            return self._error(str(exc), status=403)
        except RedirectWarning as exc:
            message = exc.args[0] if exc.args else str(exc)
            return self._error(message, status=400)
        except (UserError, ValidationError) as exc:
            return self._error(str(exc), status=400)
        except Exception:
            _logger.exception("FTIQ CRM mobile API unexpected failure")
            return self._error(_("Internal server error."), status=500)

    def _json(self, data=None, status=200):
        return request.make_json_response(data or {}, status=status)

    def _error(self, message, status=400, errors=None):
        payload = {
            "error": True,
            "detail": message,
            "message": message,
        }
        if errors is not None:
            payload["errors"] = errors
        return request.make_json_response(payload, status=status)

    def _ok_message(self, message, status=200, **extra):
        payload = {"error": False, "message": message}
        payload.update(extra)
        return self._json(payload, status=status)

    def _apply_request_lang(self):
        header_value = (
            request.httprequest.headers.get("X-FTIQ-Lang")
            or request.httprequest.headers.get("Accept-Language")
            or ""
        )
        normalized = header_value.split(",")[0].split(";")[0].strip().lower()
        normalized = normalized.replace("_", "-")
        if normalized.startswith("ar"):
            request.update_context(lang="ar_001")
        elif normalized.startswith("en"):
            request.update_context(lang="en_US")

    def _json_body(self):
        if not request.httprequest.data:
            return {}
        try:
            parsed = json.loads(request.httprequest.data.decode("utf-8"))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _arg(self, key, default=None):
        value = request.httprequest.args.get(key)
        if value in (None, ""):
            return default
        return value

    def _arg_int(self, key, default=0):
        value = self._arg(key)
        if value in (None, ""):
            return default
        try:
            return int(value)
        except Exception:
            return default

    def _limit_offset(self):
        limit = self._arg_int("limit", 20)
        offset = self._arg_int("offset", 0)
        return max(1, min(limit, 100)), max(offset, 0)

    def _request_database(self):
        for candidate in (
            request.httprequest.headers.get("X-Odoo-Database"),
            request.httprequest.headers.get("X-FTIQ-Database"),
            request.httprequest.args.get("db"),
        ):
            value = (candidate or "").strip()
            if value:
                return value
        return (request.session.db or request.db or "").strip()

    def _bearer_token(self):
        header_value = (request.httprequest.headers.get("Authorization") or "").strip()
        if not header_value.lower().startswith("bearer "):
            return ""
        return header_value[7:].strip()

    def _b64_encode(self, raw):
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    def _b64_decode(self, raw):
        padding = "=" * (-len(raw) % 4)
        return base64.urlsafe_b64decode((raw + padding).encode("ascii"))

    def _token_secret(self, env=None):
        env = env or request.env
        params = env["ir.config_parameter"].sudo()
        secret = params.get_param("ftiq_crm_mobile_api.token_secret")
        if not secret:
            secret = params.get_param("database.secret") or uuid.uuid4().hex
            params.set_param("ftiq_crm_mobile_api.token_secret", secret)
        return secret.encode("utf-8")

    def _sign_token_parts(self, signing_input, env=None):
        digest = hmac.new(
            self._token_secret(env),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        return self._b64_encode(digest)

    def _issue_token(self, user, env=None):
        env = env or request.env
        now = int(time.time())
        db = self._request_database() or request.db or request.session.db or ""
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": str(user.id),
            "uid": user.id,
            "login": user.login or user.email or "",
            "db": db,
            "iat": now,
            "exp": now + self._TOKEN_TTL_SECONDS,
        }
        encoded_header = self._b64_encode(
            json.dumps(header, separators=(",", ":")).encode("utf-8")
        )
        encoded_payload = self._b64_encode(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )
        signing_input = "%s.%s" % (encoded_header, encoded_payload)
        signature = self._sign_token_parts(signing_input, env)
        return "%s.%s" % (signing_input, signature)

    def _decode_token_payload(self, token):
        parts = (token or "").split(".")
        if len(parts) != 3:
            raise AccessDenied(_("Invalid mobile token."))
        signing_input = "%s.%s" % (parts[0], parts[1])
        expected = self._sign_token_parts(signing_input)
        if not hmac.compare_digest(expected, parts[2]):
            raise AccessDenied(_("Invalid mobile token signature."))
        payload = json.loads(self._b64_decode(parts[1]).decode("utf-8"))
        if int(payload.get("exp") or 0) <= int(time.time()):
            raise AccessDenied(_("Mobile token expired."))
        token_db = (payload.get("db") or "").strip()
        current_db = self._request_database()
        if token_db and current_db and token_db != current_db:
            raise AccessDenied(_("Mobile token database mismatch."))
        return payload

    def _authenticate(self):
        token = self._bearer_token()
        if not token:
            raise AccessDenied(_("Authentication required."))
        payload = self._decode_token_payload(token)
        uid = int(payload.get("uid") or 0)
        user = request.env["res.users"].sudo().browse(uid).exists()
        if not user or not user.active or user.share:
            raise AccessDenied(_("Invalid mobile user."))
        request.update_env(user=user.id)
        return request.env.user

    def _has_model(self, model_name):
        try:
            request.env[model_name]
            return True
        except KeyError:
            return False

    def _date_string(self, value):
        if not value:
            return None
        if isinstance(value, datetime):
            return fields.Datetime.to_string(value)
        if isinstance(value, date):
            return fields.Date.to_string(value)
        return str(value)

    def _display_date(self, record, field_name):
        if field_name not in record._fields:
            return None
        try:
            return self._date_string(record[field_name])
        except AccessError:
            return None

    def _field_value(self, record, field_name, default=None):
        if not record or field_name not in record._fields:
            return default
        try:
            value = record[field_name]
        except AccessError:
            return default
        return default if value is False else value

    def _record_name(self, record, default=""):
        if not record:
            return default
        return (
            self._field_value(record, "display_name")
            or self._field_value(record, "name")
            or default
        )

    def _record_flag(self, record, field_name, default=False):
        value = self._field_value(record, field_name, default)
        if value in (None, False):
            return default
        return bool(value)

    def _safe_search(
        self,
        model_name,
        domain=None,
        *,
        limit=None,
        offset=0,
        order=None,
        active_test=None,
    ):
        model = request.env[model_name]
        if active_test is not None:
            model = model.with_context(active_test=active_test)
        try:
            return model.search(
                domain or [],
                limit=limit,
                offset=offset,
                order=order,
            )
        except AccessError:
            return model.browse()

    def _safe_search_count(self, model_name, domain=None, *, active_test=None):
        model = request.env[model_name]
        if active_test is not None:
            model = model.with_context(active_test=active_test)
        try:
            return model.search_count(domain or [])
        except AccessError:
            return 0

    def _payload_float(self, payload, key, default=None):
        if key not in payload or payload.get(key) in (None, ""):
            return default
        try:
            return float(payload.get(key))
        except Exception:
            return default

    def _payload_bool(self, payload, key, default=False):
        if key not in payload:
            return default
        value = payload.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _location_payload(self, payload):
        if not isinstance(payload, dict):
            return {}
        if "latitude" not in payload or "longitude" not in payload:
            return {}
        latitude = self._payload_float(payload, "latitude")
        longitude = self._payload_float(payload, "longitude")
        if latitude is None or longitude is None:
            return {}
        return {
            "ftiq_mobile_latitude": latitude,
            "ftiq_mobile_longitude": longitude,
            "ftiq_mobile_accuracy": self._payload_float(payload, "accuracy", 0.0) or 0.0,
            "ftiq_mobile_is_mock": self._payload_bool(payload, "is_mock", False),
            "ftiq_mobile_location_at": fields.Datetime.now(),
        }

    def _apply_mobile_location(self, record, payload, partner=None):
        location_values = self._location_payload(payload)
        if not location_values:
            return
        record_values = {
            key: value
            for key, value in location_values.items()
            if key in getattr(record, "_fields", {})
        }
        if record_values:
            record.with_context(ftiq_mobile_location_write=True).write(record_values)
        partner = partner or (
            record.partner_id.commercial_partner_id
            if getattr(record, "_fields", {}).get("partner_id") and record.partner_id
            else request.env["res.partner"]
        )
        if not partner:
            return
        partner_values = {}
        if "partner_latitude" in partner._fields:
            partner_values["partner_latitude"] = location_values["ftiq_mobile_latitude"]
        if "partner_longitude" in partner._fields:
            partner_values["partner_longitude"] = location_values["ftiq_mobile_longitude"]
        if "ftiq_mobile_last_location_accuracy" in partner._fields:
            partner_values["ftiq_mobile_last_location_accuracy"] = location_values["ftiq_mobile_accuracy"]
        if "ftiq_mobile_last_location_is_mock" in partner._fields:
            partner_values["ftiq_mobile_last_location_is_mock"] = location_values["ftiq_mobile_is_mock"]
        if "ftiq_mobile_last_location_at" in partner._fields:
            partner_values["ftiq_mobile_last_location_at"] = location_values["ftiq_mobile_location_at"]
        if partner_values:
            partner.with_context(ftiq_mobile_location_write=True).write(partner_values)

    def _record_mobile_location(self, record):
        return {
            "latitude": self._field_value(record, "ftiq_mobile_latitude"),
            "longitude": self._field_value(record, "ftiq_mobile_longitude"),
            "accuracy": self._field_value(record, "ftiq_mobile_accuracy"),
            "is_mock": bool(self._field_value(record, "ftiq_mobile_is_mock", False)),
            "location_at": self._display_date(record, "ftiq_mobile_location_at"),
        }

    def _partner_mobile_location(self, partner):
        latitude = self._field_value(partner, "partner_latitude")
        longitude = self._field_value(partner, "partner_longitude")
        return {
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": self._field_value(partner, "ftiq_mobile_last_location_accuracy"),
            "is_mock": bool(self._field_value(partner, "ftiq_mobile_last_location_is_mock", False)),
            "location_at": self._display_date(partner, "ftiq_mobile_last_location_at"),
        }

    def _open_invoice_domain(self, commercial_partner_ids):
        return [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
            ("partner_id", "child_of", commercial_partner_ids),
        ]

    def _invoice_metrics_by_partner(self, partners):
        commercial_partner_ids = list(
            {
                commercial.id
                for partner in partners
                for commercial in [self._field_value(partner, "commercial_partner_id")]
                if partner and commercial
            }
        )
        if not commercial_partner_ids or not self._has_model("account.move"):
            return {}
        moves = self._safe_search(
            "account.move",
            self._open_invoice_domain(commercial_partner_ids),
        )
        company_currency = self._record_name(
            self._field_value(request.env.company, "currency_id"),
            "",
        )
        metrics = {
            partner_id: {
                "due_amount": 0.0,
                "due_amount_company": 0.0,
                "open_invoice_count": 0,
                "_currencies": set(),
                "currency": company_currency,
                "currency_count": 0,
            }
            for partner_id in commercial_partner_ids
        }
        for move in moves:
            move_partner = self._field_value(move, "partner_id")
            partner = self._field_value(move_partner, "commercial_partner_id") if move_partner else False
            if not partner:
                continue
            values = metrics.setdefault(
                partner.id,
                {
                    "due_amount": 0.0,
                    "due_amount_company": 0.0,
                    "open_invoice_count": 0,
                    "_currencies": set(),
                    "currency": company_currency,
                    "currency_count": 0,
                },
            )
            values["due_amount"] += self._field_value(move, "amount_residual", 0.0) or 0.0
            values["due_amount_company"] += abs(
                self._field_value(move, "amount_residual_signed", 0.0) or 0.0
            )
            values["open_invoice_count"] += 1
            currency = self._field_value(move, "currency_id")
            values["_currencies"].add(
                self._record_name(currency, company_currency) if currency else company_currency
            )
        for values in metrics.values():
            currencies = sorted(values.pop("_currencies", set()))
            values["currency_count"] = len(currencies)
            if len(currencies) == 1:
                values["currency"] = currencies[0]
            else:
                values["currency"] = company_currency
                values["due_amount"] = values["due_amount_company"]
            values.pop("due_amount_company", None)
        return metrics

    def _serialize_invoice_summary(self, move):
        currency = self._field_value(move, "currency_id")
        return {
            "id": move.id,
            "name": self._record_name(move),
            "number": self._field_value(move, "name", "") or "",
            "amount_total": self._field_value(move, "amount_total", 0.0) or 0.0,
            "amount_residual": self._field_value(move, "amount_residual", 0.0) or 0.0,
            "currency": self._record_name(
                currency,
                self._record_name(
                    self._field_value(request.env.company, "currency_id"),
                    "",
                ),
            ),
            "invoice_date": self._date_string(self._field_value(move, "invoice_date")),
            "due_date": self._date_string(self._field_value(move, "invoice_date_due")),
            "payment_state": self._field_value(move, "payment_state", "") or "",
        }

    def _serialize_mail_notification(self, notification):
        payload = notification._ftiq_mobile_payload()
        related_model = payload["data"].get("target_model", "")
        related_id = payload["data"].get("target_id", "")
        notification_type = "system"
        if related_model == "project.task":
            notification_type = "taskAssigned"
        elif related_model == "crm.lead":
            notification_type = "dealStageChanged"
        elif related_model == "sale.order":
            notification_type = "salesOrder"
        return {
            "id": str(notification.id),
            "type": notification_type,
            "title": payload["title"],
            "message": payload["body"] or payload["title"],
            "is_read": bool(notification.is_read),
            "created_at": self._date_string(
                notification.mail_message_id.date
                if notification.mail_message_id
                else notification.create_date
            ),
            "category": related_model or "system",
            "target_model": related_model,
            "target_id": related_id,
            "target_route": payload["data"].get("target_route", ""),
            "related_client_id": payload["data"].get("related_client_id", ""),
            "record_name": notification.mail_message_id.record_name if notification.mail_message_id else "",
        }

    def _selection_label(self, record, field_name, value=None):
        if not record or field_name not in record._fields:
            return ""
        field = record._fields[field_name]
        try:
            key = value if value is not None else record[field_name]
        except AccessError:
            return ""
        return dict(field.selection).get(key, key or "")

    def _split_name(self, name):
        parts = (name or "").strip().split()
        if not parts:
            return "", ""
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], " ".join(parts[1:])

    def _assigned_users(self, users):
        return [
            {
                "id": str(user.id),
                "user__email": self._field_value(user, "login", "") or self._field_value(user, "email", "") or "",
                "name": self._record_name(user, "") or self._field_value(user, "login", "") or "",
                "user": {
                    "id": str(user.id),
                    "email": self._field_value(user, "login", "") or self._field_value(user, "email", "") or "",
                    "name": self._record_name(user, "") or self._field_value(user, "login", "") or "",
                    "profile_pic": "",
                },
                "user_details": {
                    "id": str(user.id),
                    "email": self._field_value(user, "login", "") or self._field_value(user, "email", "") or "",
                    "name": self._record_name(user, "") or self._field_value(user, "login", "") or "",
                    "profile_pic": "",
                },
                "role": "ADMIN" if user.has_group("base.group_system") else "USER",
                "is_active": self._record_flag(user, "active", False),
            }
            for user in users
        ]

    def _serialize_user(self, user):
        if not user:
            return {
                "id": "",
                "email": "",
                "name": "",
                "profileImage": "",
            }
        return {
            "id": str(user.id),
            "email": self._field_value(user, "login", "") or self._field_value(user, "email", "") or "",
            "name": self._record_name(user, "") or self._field_value(user, "login", "") or "",
            "profileImage": "",
        }

    def _serialize_profile(self, user):
        if not user:
            return {
                "id": "",
                "user_details": {
                    "id": "",
                    "email": "",
                    "profile_pic": "",
                },
                "email": "",
                "role": "USER",
                "is_active": False,
                "created_at": None,
            }
        return {
            "id": str(user.id),
            "user_details": {
                "id": str(user.id),
                "email": self._field_value(user, "login", "") or self._field_value(user, "email", "") or "",
                "name": self._record_name(user, "") or self._field_value(user, "login", "") or "",
                "profile_pic": "",
            },
            "email": self._field_value(user, "login", "") or self._field_value(user, "email", "") or "",
            "name": self._record_name(user, "") or self._field_value(user, "login", "") or "",
            "role": "ADMIN" if user.has_group("base.group_system") else "USER",
            "is_active": self._record_flag(user, "active", False),
            "created_at": self._date_string(self._field_value(user, "create_date")),
        }

    def _serialize_team(self, team):
        return {
            "id": str(team.id),
            "name": self._record_name(team),
            "description": self._field_value(team, "description", "") or "",
            "users": self._assigned_users(
                (self._field_value(team, "member_ids") or request.env["res.users"])
                | ((self._field_value(team, "user_id") or request.env["res.users"])[:1])
            ),
            "created_at": self._date_string(self._field_value(team, "create_date")),
            "created_by": self._serialize_user(self._field_value(team, "create_uid")),
        }

    def _slug(self, value):
        return (value or "").strip().lower().replace(" ", "-")

    def _serialize_tag(self, tag):
        color = self._field_value(tag, "color", False)
        name = self._record_name(tag)
        return {
            "id": str(tag.id),
            "name": name,
            "slug": self._slug(name),
            "color": str(color if color not in (False, None) else "gray"),
            "is_active": self._record_flag(tag, "active", True),
            "created_at": self._date_string(self._field_value(tag, "create_date")),
        }

    def _rating_from_priority(self, priority):
        value = str(priority or "").strip()
        if value in {"3", "2"}:
            return "HOT"
        if value == "1":
            return "WARM"
        return "COLD"

    def _priority_from_rating(self, rating):
        normalized = (rating or "").strip().upper()
        if normalized == "HOT":
            return "3"
        if normalized == "WARM":
            return "1"
        return "0"

    def _lead_source_value(self, lead):
        source = self._field_value(lead, "source_id")
        if source:
            return (self._record_name(source) or "").strip().lower() or "other"
        return ""

    def _lead_status_value(self, lead):
        if not self._record_flag(lead, "active", True):
            return "closed"
        if self._field_value(lead, "type", "") == "opportunity":
            return "converted"
        stage = self._field_value(lead, "stage_id")
        stage_name = (self._field_value(stage, "name", "") or "").strip().lower() if stage else ""
        if any(token in stage_name for token in ("process", "qual", "opportun")):
            return "in process"
        return "assigned"

    def _deal_stage_value(self, lead):
        if not self._record_flag(lead, "active", True):
            return "CLOSED_LOST"
        stage = self._field_value(lead, "stage_id")
        stage_name = (self._field_value(stage, "name", "") or "").strip().lower() if stage else ""
        if self._field_value(stage, "is_won", False):
            return "CLOSED_WON"
        if "lost" in stage_name:
            return "CLOSED_LOST"
        if "won" in stage_name:
            return "CLOSED_WON"
        if "negoti" in stage_name:
            return "NEGOTIATION"
        if "propos" in stage_name or "quote" in stage_name:
            return "PROPOSAL"
        if "qual" in stage_name:
            return "QUALIFICATION"
        return "PROSPECTING"

    def _stage_label(self, code):
        return {
            "PROSPECTING": "Prospecting",
            "QUALIFICATION": "Qualified",
            "PROPOSAL": "Proposal",
            "NEGOTIATION": "Negotiation",
            "CLOSED_WON": "Closed Won",
            "CLOSED_LOST": "Closed Lost",
        }.get(code, code)

    def _serialize_partner_account(self, partner):
        commercial = self._field_value(partner, "commercial_partner_id", partner) or partner
        country = self._field_value(commercial, "country_id") or self._field_value(partner, "country_id")
        state = self._field_value(commercial, "state_id") or self._field_value(partner, "state_id")
        company = self._field_value(commercial, "company_id")
        company_currency = self._field_value(company, "currency_id") if company else False
        user = self._field_value(commercial, "user_id")
        tags = self._field_value(commercial, "category_id") or request.env["res.partner.category"]
        location = self._partner_mobile_location(commercial)
        return {
            "id": str(commercial.id),
            "name": self._record_name(commercial),
            "email": self._field_value(commercial, "email", "") or "",
            "phone": self._field_value(commercial, "phone", "") or self._field_value(commercial, "mobile", "") or "",
            "website": self._field_value(commercial, "website", "") or "",
            "industry": "",
            "number_of_employees": 0,
            "annual_revenue": 0,
            "currency": self._record_name(
                company_currency,
                self._record_name(
                    self._field_value(request.env.company, "currency_id"),
                    "",
                ),
            )
            if company_currency
            else self._record_name(
                self._field_value(request.env.company, "currency_id"),
                "",
            ),
            "address_line": self._field_value(commercial, "street", "") or "",
            "city": self._field_value(commercial, "city", "") or "",
            "state": self._record_name(state) if state else "",
            "postcode": self._field_value(commercial, "zip", "") or "",
            "country": self._record_name(country) if country else "",
            "country_display": self._record_name(country) if country else "",
            "assigned_to": self._assigned_users(user) if user else [],
            "contacts": [],
            "tags": [self._serialize_tag(tag) for tag in tags],
            "description": self._field_value(commercial, "comment", "") or "",
            "created_at": self._date_string(self._field_value(commercial, "create_date")),
            "is_active": self._record_flag(commercial, "active", True),
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "location_accuracy": location["accuracy"],
            "location_is_mock": location["is_mock"],
            "location_at": location["location_at"],
        }

    def _serialize_partner_contact(self, partner):
        first_name, last_name = self._split_name(self._field_value(partner, "name", "") or "")
        parent = self._field_value(partner, "parent_id")
        commercial = self._field_value(partner, "commercial_partner_id", partner) or partner
        account = parent or (commercial if self._field_value(partner, "is_company", False) is False else False)
        country = self._field_value(partner, "country_id")
        state = self._field_value(partner, "state_id")
        user = self._field_value(partner, "user_id")
        tags = self._field_value(partner, "category_id") or request.env["res.partner.category"]
        location = self._partner_mobile_location(commercial)
        return {
            "id": str(partner.id),
            "name": self._record_name(partner),
            "first_name": first_name,
            "last_name": last_name,
            "email": self._field_value(partner, "email", "") or "",
            "primary_email": self._field_value(partner, "email", "") or "",
            "phone": self._field_value(partner, "phone", "") or self._field_value(partner, "mobile", "") or "",
            "mobile_number": self._field_value(partner, "mobile", "") or self._field_value(partner, "phone", "") or "",
            "organization": self._record_name(account) if account else "",
            "title": self._field_value(partner, "function", "") or "",
            "department": "",
            "do_not_call": False,
            "linkedin_url": "",
            "address_line": self._field_value(partner, "street", "") or "",
            "city": self._field_value(partner, "city", "") or "",
            "state": self._record_name(state) if state else "",
            "postcode": self._field_value(partner, "zip", "") or "",
            "country": self._record_name(country) if country else "",
            "assigned_to": self._assigned_users(user) if user else [],
            "tags": [self._serialize_tag(tag) for tag in tags],
            "description": self._field_value(partner, "comment", "") or "",
            "created_at": self._date_string(self._field_value(partner, "create_date")),
            "is_active": self._record_flag(partner, "active", True),
            "account": str(account.id) if account else None,
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "location_accuracy": location["accuracy"],
            "location_is_mock": location["is_mock"],
            "location_at": location["location_at"],
        }

    def _serialize_lead(self, lead):
        contact_name = self._field_value(lead, "contact_name", "") or ""
        partner = self._field_value(lead, "partner_id")
        if not contact_name and partner:
            contact_name = self._field_value(partner, "name", "") or ""
        first_name, last_name = self._split_name(contact_name)
        company_name = (
            self._field_value(lead, "partner_name", "")
            or (
                self._field_value(
                    self._field_value(partner, "commercial_partner_id"),
                    "name",
                    "",
                )
                if partner
                else ""
            )
            or ""
        )
        user = self._field_value(lead, "user_id")
        country = self._field_value(lead, "country_id")
        state = self._field_value(lead, "state_id")
        currency = self._field_value(lead, "company_currency")
        tags = self._field_value(lead, "tag_ids") or request.env["crm.tag"]
        return {
            "id": str(lead.id),
            "title": self._field_value(lead, "name", "") or "",
            "salutation": "",
            "first_name": first_name,
            "last_name": last_name,
            "email": self._field_value(lead, "email_from", "") or "",
            "phone": self._field_value(lead, "phone", "") or self._field_value(lead, "mobile", "") or "",
            "job_title": self._field_value(lead, "function", "") or "",
            "website": self._field_value(lead, "website", "") or "",
            "linkedin_url": "",
            "company_name": company_name,
            "status": self._lead_status_value(lead),
            "source": self._lead_source_value(lead),
            "rating": self._rating_from_priority(self._field_value(lead, "priority", "")),
            "industry": "",
            "opportunity_amount": self._field_value(lead, "expected_revenue", 0.0) or 0.0,
            "currency": self._record_name(
                currency,
                self._record_name(
                    self._field_value(request.env.company, "currency_id"),
                    "",
                ),
            ),
            "probability": int(self._field_value(lead, "probability", 0) or 0),
            "close_date": self._display_date(lead, "date_deadline"),
            "address_line": self._field_value(lead, "street", "") or "",
            "city": self._field_value(lead, "city", "") or "",
            "state": self._record_name(state) if state else "",
            "postcode": self._field_value(lead, "zip", "") or "",
            "country": self._record_name(country) if country else "",
            "last_contacted": self._display_date(lead, "date_last_stage_update"),
            "next_follow_up": self._display_date(lead, "activity_date_deadline"),
            "description": self._field_value(lead, "description", "") or "",
            "tags": [self._serialize_tag(tag) for tag in tags],
            "assigned_to": self._assigned_users(user) if user else [],
            "lead_comments": self._serialize_messages(lead),
            "created_by": self._serialize_user(self._field_value(lead, "create_uid")),
            "created_at": self._date_string(self._field_value(lead, "create_date")),
            "updated_at": self._date_string(self._field_value(lead, "write_date")),
            "is_active": self._record_flag(lead, "active", True),
            **self._record_mobile_location(lead),
        }

    def _serialize_opportunity(self, lead):
        lead_partner = self._field_value(lead, "partner_id")
        partner = self._field_value(lead_partner, "commercial_partner_id") if lead_partner else False
        user = self._field_value(lead, "user_id")
        currency = self._field_value(lead, "company_currency")
        contact_partner = (
            lead_partner
            if lead_partner and not self._field_value(lead_partner, "is_company", False)
            else False
        )
        tags = self._field_value(lead, "tag_ids") or request.env["crm.tag"]
        team = self._field_value(lead, "team_id")
        return {
            "id": str(lead.id),
            "name": self._field_value(lead, "name", "") or "",
            "account": self._serialize_partner_account(partner) if partner else None,
            "stage": self._deal_stage_value(lead),
            "opportunity_type": "NEW_BUSINESS",
            "currency": self._record_name(
                currency,
                self._record_name(
                    self._field_value(request.env.company, "currency_id"),
                    "",
                ),
            ),
            "amount": self._field_value(lead, "expected_revenue", 0.0) or 0.0,
            "amount_source": "manual",
            "probability": int(self._field_value(lead, "probability", 0) or 0),
            "closed_on": self._display_date(lead, "date_deadline"),
            "lead_source": self._lead_source_value(lead).upper() or "NONE",
            "contacts": [self._serialize_partner_contact(contact_partner)] if contact_partner else [],
            "line_items": [],
            "line_items_total": 0.0,
            "assigned_to": self._assigned_users(user) if user else [],
            "closed_by": None,
            "tags": [self._serialize_tag(tag) for tag in tags],
            "description": self._field_value(lead, "description", "") or "",
            "created_by": self._serialize_user(self._field_value(lead, "create_uid")),
            "created_at": self._date_string(self._field_value(lead, "create_date")),
            "updated_at": self._date_string(self._field_value(lead, "write_date")),
            "is_active": self._record_flag(lead, "active", True),
            "org": {"id": str(request.env.company.id), "name": self._record_name(request.env.company)},
            "teams": [self._serialize_team(team)] if team else [],
            **self._record_mobile_location(lead),
        }

    def _task_state_code(self, task):
        if not task or "state" not in task._fields:
            return ""
        # In some databases, reading task.state triggers stage access on
        # project.task.type. Read the narrow field under sudo so task
        # serialization does not fail for otherwise valid users.
        try:
            return (task.sudo()["state"] or "").strip()
        except AccessError:
            return ""
        except Exception:
            return ""

    def _task_status_value(self, task, state_value=None):
        state_value = state_value if state_value is not None else self._task_state_code(task)
        if state_value:
            state_label = self._task_state_label(task, state_value=state_value)
            if state_label:
                return state_label
        return "New"

    def _task_state_label(self, task, state_value=None):
        if "state" not in task._fields:
            return ""
        state_value = state_value if state_value is not None else self._task_state_code(task)
        if not state_value:
            return ""
        selection = dict(task._fields["state"]._description_selection(request.env))
        return selection.get(state_value, state_value)

    def _task_state_options(self, task):
        if "state" not in task._fields:
            return []
        return [
            {
                "value": value,
                "label": label,
                "is_done": value == "1_done",
                "is_cancelled": value == "1_canceled",
                "sequence": index,
            }
            for index, (value, label) in enumerate(
                task._fields["state"]._description_selection(request.env)
            )
        ]

    def _task_priority_value(self, task):
        priority = str(self._field_value(task, "priority", "") or "")
        if priority in {"2", "3"}:
            return "High"
        if priority == "1":
            return "Medium"
        return "Low"

    def _serialize_task(self, task):
        partner = self._field_value(task, "partner_id")
        users = self._field_value(task, "user_ids") or request.env["res.users"]
        tags = self._field_value(task, "tag_ids") or request.env["project.tags"]
        description = html2plaintext(self._field_value(task, "description", "") or "").strip()
        state_value = self._task_state_code(task)
        task_type = self._field_value(task, "ftiq_mobile_task_type", "") or ""
        visit_state = self._field_value(task, "ftiq_mobile_visit_state", "") or ""
        execution_payload = {}
        raw_execution_payload = self._field_value(task, "ftiq_mobile_execution_payload", "") or ""
        if raw_execution_payload:
            try:
                parsed_execution_payload = json.loads(raw_execution_payload)
                if isinstance(parsed_execution_payload, dict):
                    execution_payload = parsed_execution_payload
            except Exception:
                execution_payload = {}
        return {
            "id": str(task.id),
            "title": self._field_value(task, "name", "") or "",
            "status": self._task_status_value(task, state_value=state_value),
            "status_code": state_value,
            "status_options": self._task_state_options(task),
            "stage_id": "",
            "stage": "",
            "priority": self._task_priority_value(task),
            "due_date": self._display_date(task, "date_deadline"),
            "description": description,
            "task_type": task_type,
            "task_type_label": self._selection_label(task, "ftiq_mobile_task_type", task_type),
            "visit_state": visit_state,
            "visit_state_label": self._selection_label(task, "ftiq_mobile_visit_state", visit_state),
            "visit_started_at": self._display_date(task, "ftiq_mobile_started_at"),
            "visit_completed_at": self._display_date(task, "ftiq_mobile_completed_at"),
            "execution_payload": execution_payload,
            "account": self._serialize_partner_account(partner) if partner else None,
            "opportunity": None,
            "case": None,
            "lead": None,
            "created_by": self._serialize_user(self._field_value(task, "create_uid")),
            "created_at": self._date_string(self._field_value(task, "create_date")),
            "updated_at": self._date_string(self._field_value(task, "write_date")),
            "contacts": [],
            "teams": [],
            "assigned_to": self._assigned_users(users),
            "tags": [self._serialize_tag(tag) for tag in tags],
            "task_attachment": [],
            "task_comments": self._serialize_messages(task),
            **self._record_mobile_location(task),
        }

    def _serialize_messages(self, record):
        if "message_ids" not in record._fields:
            return []
        messages = self._field_value(record, "message_ids", request.env["mail.message"])
        if not messages:
            return []
        try:
            messages = messages.filtered(lambda msg: (self._field_value(msg, "message_type", "") or "") == "comment")[:10]
        except AccessError:
            return []
        result = []
        for message in messages:
            author = self._field_value(message, "author_id")
            user_email = (
                self._field_value(author, "email", "")
                or self._field_value(author, "name", "")
                or ""
            )
            result.append(
                {
                    "id": str(message.id),
                    "comment": self._field_value(message, "body", "") or "",
                    "commented_on": self._date_string(self._field_value(message, "date")),
                    "commented_by": {
                        "id": str(author.id) if author else "",
                        "user_details": {
                            "email": user_email,
                            "profile_pic": "",
                        },
                    },
                }
            )
        return result

    def _domain_for_search(self, fields_to_search, search):
        if not search:
            return []
        clauses = [[(field_name, "ilike", search)] for field_name in fields_to_search]
        return expression.OR(clauses) if clauses else []
