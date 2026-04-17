import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import date, datetime

from odoo import _, fields, http
from odoo.exceptions import AccessDenied, AccessError, UserError, ValidationError
from odoo.http import request
from odoo.osv import expression


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
        return self._date_string(record[field_name])

    def _field_value(self, record, field_name, default=None):
        if not record or field_name not in record._fields:
            return default
        value = record[field_name]
        return default if value is False else value

    def _selection_label(self, record, field_name, value=None):
        if not record or field_name not in record._fields:
            return ""
        field = record._fields[field_name]
        key = value if value is not None else record[field_name]
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
                "user__email": user.login or user.email or "",
                "user": {
                    "id": str(user.id),
                    "email": user.login or user.email or "",
                    "profile_pic": "",
                },
                "user_details": {
                    "id": str(user.id),
                    "email": user.login or user.email or "",
                    "profile_pic": "",
                },
                "role": "ADMIN" if user.has_group("base.group_system") else "USER",
                "is_active": bool(user.active),
            }
            for user in users
        ]

    def _serialize_user(self, user):
        return {
            "id": str(user.id),
            "email": user.login or user.email or "",
            "name": user.name or user.login or "",
            "profileImage": "",
        }

    def _serialize_profile(self, user):
        return {
            "id": str(user.id),
            "user_details": {
                "id": str(user.id),
                "email": user.login or user.email or "",
                "profile_pic": "",
            },
            "email": user.login or user.email or "",
            "role": "ADMIN" if user.has_group("base.group_system") else "USER",
            "is_active": bool(user.active),
            "created_at": self._date_string(user.create_date),
        }

    def _serialize_team(self, team):
        return {
            "id": str(team.id),
            "name": team.display_name,
            "description": "",
            "users": self._assigned_users(team.member_ids | team.user_id),
            "created_at": self._date_string(team.create_date),
            "created_by": self._serialize_user(team.create_uid),
        }

    def _slug(self, value):
        return (value or "").strip().lower().replace(" ", "-")

    def _serialize_tag(self, tag):
        color = getattr(tag, "color", False)
        return {
            "id": str(tag.id),
            "name": tag.display_name,
            "slug": self._slug(tag.display_name),
            "color": str(color if color not in (False, None) else "gray"),
            "is_active": bool(getattr(tag, "active", True)),
            "created_at": self._date_string(tag.create_date),
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
            return (source.name or "").strip().lower() or "other"
        return ""

    def _lead_status_value(self, lead):
        if not getattr(lead, "active", True):
            return "closed"
        if getattr(lead, "type", "") == "opportunity":
            return "converted"
        stage_name = (lead.stage_id.name or "").strip().lower() if lead.stage_id else ""
        if any(token in stage_name for token in ("process", "qual", "opportun")):
            return "in process"
        return "assigned"

    def _deal_stage_value(self, lead):
        if not getattr(lead, "active", True):
            return "CLOSED_LOST"
        stage = lead.stage_id
        stage_name = (stage.name or "").strip().lower() if stage else ""
        if getattr(stage, "is_won", False):
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
        commercial = partner.commercial_partner_id or partner
        country = partner.country_id
        state = partner.state_id
        return {
            "id": str(commercial.id),
            "name": commercial.display_name,
            "email": commercial.email or "",
            "phone": commercial.phone or commercial.mobile or "",
            "website": commercial.website or "",
            "industry": "",
            "number_of_employees": 0,
            "annual_revenue": 0,
            "currency": commercial.company_id.currency_id.name
            if commercial.company_id and commercial.company_id.currency_id
            else request.env.company.currency_id.name,
            "address_line": commercial.street or "",
            "city": commercial.city or "",
            "state": state.name if state else "",
            "postcode": commercial.zip or "",
            "country": country.name if country else "",
            "country_display": country.name if country else "",
            "assigned_to": self._assigned_users(commercial.user_id) if commercial.user_id else [],
            "contacts": [],
            "tags": [self._serialize_tag(tag) for tag in commercial.category_id],
            "description": commercial.comment or "",
            "created_at": self._date_string(commercial.create_date),
            "is_active": bool(commercial.active),
        }

    def _serialize_partner_contact(self, partner):
        first_name, last_name = self._split_name(partner.name)
        account = partner.parent_id or (partner.commercial_partner_id if partner.is_company is False else False)
        country = partner.country_id
        state = partner.state_id
        return {
            "id": str(partner.id),
            "first_name": first_name,
            "last_name": last_name,
            "email": partner.email or "",
            "primary_email": partner.email or "",
            "phone": partner.phone or partner.mobile or "",
            "mobile_number": partner.mobile or partner.phone or "",
            "organization": account.display_name if account else "",
            "title": partner.function or "",
            "department": "",
            "do_not_call": False,
            "linkedin_url": "",
            "address_line": partner.street or "",
            "city": partner.city or "",
            "state": state.name if state else "",
            "postcode": partner.zip or "",
            "country": country.name if country else "",
            "assigned_to": self._assigned_users(partner.user_id) if partner.user_id else [],
            "tags": [self._serialize_tag(tag) for tag in partner.category_id],
            "description": partner.comment or "",
            "created_at": self._date_string(partner.create_date),
            "is_active": bool(partner.active),
            "account": str(account.id) if account else None,
        }

    def _serialize_lead(self, lead):
        contact_name = self._field_value(lead, "contact_name", "") or ""
        if not contact_name:
            contact_name = lead.partner_id.name if lead.partner_id else ""
        first_name, last_name = self._split_name(contact_name)
        company_name = (
            self._field_value(lead, "partner_name", "")
            or (lead.partner_id.commercial_partner_id.name if lead.partner_id else "")
            or ""
        )
        user = self._field_value(lead, "user_id")
        country = self._field_value(lead, "country_id")
        state = self._field_value(lead, "state_id")
        currency = self._field_value(lead, "company_currency")
        return {
            "id": str(lead.id),
            "title": lead.name or "",
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
            "currency": currency.name if currency else request.env.company.currency_id.name,
            "probability": int(self._field_value(lead, "probability", 0) or 0),
            "close_date": self._display_date(lead, "date_deadline"),
            "address_line": self._field_value(lead, "street", "") or "",
            "city": self._field_value(lead, "city", "") or "",
            "state": state.name if state else "",
            "postcode": self._field_value(lead, "zip", "") or "",
            "country": country.name if country else "",
            "last_contacted": self._display_date(lead, "date_last_stage_update"),
            "next_follow_up": self._display_date(lead, "date_action_next"),
            "description": self._field_value(lead, "description", "") or "",
            "tags": [self._serialize_tag(tag) for tag in lead.tag_ids],
            "assigned_to": self._assigned_users(user) if user else [],
            "lead_comments": self._serialize_messages(lead),
            "created_by": self._serialize_user(lead.create_uid),
            "created_at": self._date_string(lead.create_date),
            "updated_at": self._date_string(lead.write_date),
            "is_active": bool(getattr(lead, "active", True)),
        }

    def _serialize_opportunity(self, lead):
        partner = lead.partner_id.commercial_partner_id if lead.partner_id else False
        user = self._field_value(lead, "user_id")
        currency = self._field_value(lead, "company_currency")
        contact_partner = lead.partner_id if lead.partner_id and not lead.partner_id.is_company else False
        return {
            "id": str(lead.id),
            "name": lead.name or "",
            "account": self._serialize_partner_account(partner) if partner else None,
            "stage": self._deal_stage_value(lead),
            "opportunity_type": "NEW_BUSINESS",
            "currency": currency.name if currency else request.env.company.currency_id.name,
            "amount": self._field_value(lead, "expected_revenue", 0.0) or 0.0,
            "amount_source": "manual",
            "probability": int(self._field_value(lead, "probability", 0) or 0),
            "closed_on": self._display_date(lead, "date_deadline"),
            "lead_source": self._lead_source_value(lead).upper() or "NONE",
            "contacts": [self._serialize_partner_contact(contact_partner)] if contact_partner else [],
            "line_items": [],
            "line_items_total": 0.0,
            "assigned_to": self._assigned_users(user) if user else [],
            "teams": [self._serialize_team(lead.team_id)] if lead.team_id else [],
            "closed_by": None,
            "tags": [self._serialize_tag(tag) for tag in lead.tag_ids],
            "description": self._field_value(lead, "description", "") or "",
            "created_by": self._serialize_user(lead.create_uid),
            "created_at": self._date_string(lead.create_date),
            "updated_at": self._date_string(lead.write_date),
            "is_active": bool(getattr(lead, "active", True)),
            "org": {"id": str(request.env.company.id), "name": request.env.company.name},
        }

    def _task_status_value(self, task):
        stage = self._field_value(task, "stage_id")
        if stage and getattr(stage, "fold", False):
            return "Completed"
        stage_name = (stage.name or "").lower() if stage else ""
        if "progress" in stage_name or "doing" in stage_name:
            return "In Progress"
        if "done" in stage_name or "complete" in stage_name:
            return "Completed"
        return "New"

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
        return {
            "id": str(task.id),
            "title": task.name or "",
            "status": self._task_status_value(task),
            "priority": self._task_priority_value(task),
            "due_date": self._display_date(task, "date_deadline"),
            "description": self._field_value(task, "description", "") or "",
            "account": self._serialize_partner_account(partner) if partner else None,
            "opportunity": None,
            "case": None,
            "lead": None,
            "created_by": self._serialize_user(task.create_uid),
            "created_at": self._date_string(task.create_date),
            "updated_at": self._date_string(task.write_date),
            "contacts": [],
            "teams": [],
            "assigned_to": self._assigned_users(users),
            "tags": [self._serialize_tag(tag) for tag in tags],
            "task_attachment": [],
            "task_comments": self._serialize_messages(task),
        }

    def _serialize_messages(self, record):
        if "message_ids" not in record._fields:
            return []
        messages = record.message_ids.filtered(lambda msg: msg.message_type == "comment")[:10]
        result = []
        for message in messages:
            author = message.author_id
            user_email = author.email or author.name or ""
            result.append(
                {
                    "id": str(message.id),
                    "comment": message.body or "",
                    "commented_on": self._date_string(message.date),
                    "commented_by": {
                        "id": str(author.id),
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
