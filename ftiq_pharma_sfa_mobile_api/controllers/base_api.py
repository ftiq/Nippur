import json
import logging

import odoo.http as odoo_http
import odoo.modules.registry
from odoo import _, api, fields, http
from odoo.exceptions import AccessDenied, AccessError, UserError, ValidationError
from odoo.http import request
from odoo.osv import expression
from odoo.tools.mail import html2plaintext

from odoo.addons.ftiq_pharma_sfa.models.mobile_access import MOBILE_CATALOG_BY_FULL_KEY


_logger = logging.getLogger(__name__)


class FtiqMobileApiBase(http.Controller):
    _OWNER_FIELD_BY_MODEL = {
        "ftiq.field.attendance": "user_id",
        "ftiq.visit": "user_id",
        "ftiq.weekly.plan.line": "user_id",
        "ftiq.daily.task": "user_id",
        "ftiq.stock.check": "user_id",
        "ftiq.mobile.device": "user_id",
        "sale.order": "user_id",
        "account.payment": "ftiq_user_id",
        "hr.expense": "ftiq_user_id",
    }
    _THREAD_SUPPORTED_MODELS = {
        "ftiq.daily.task",
        "ftiq.visit",
        "ftiq.weekly.plan",
        "project.project",
        "sale.order",
        "purchase.order",
        "project.task",
        "account.payment",
        "account.move",
        "hr.expense",
        "ftiq.stock.check",
        "ftiq.team.message",
    }

    def _ok(self, data=None, meta=None, status=200):
        payload = {
            "success": True,
            "data": data or {},
            "meta": meta or {},
            "error": None,
        }
        return request.make_json_response(payload, status=status)

    def _error(self, message, status=400, code="bad_request", details=None):
        payload = {
            "success": False,
            "data": {},
            "meta": {},
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
        }
        return request.make_json_response(payload, status=status)

    def _dispatch(self, callback):
        try:
            self._apply_request_lang()
            return callback()
        except AccessDenied as exc:
            return self._error(str(exc), status=401, code="access_denied")
        except AccessError as exc:
            return self._error(str(exc), status=403, code="access_error")
        except (UserError, ValidationError) as exc:
            return self._error(str(exc), status=400, code="validation_error")
        except Exception:
            _logger.exception("FTIQ mobile API unexpected failure")
            return self._error(_("Internal server error."), status=500, code="server_error")

    def _apply_request_lang(self):
        header_value = (
            request.httprequest.headers.get("X-FTIQ-Lang")
            or request.httprequest.headers.get("Accept-Language")
            or ""
        )
        normalized = header_value.split(",")[0].split(";")[0].strip().lower().replace("_", "-")
        if normalized.startswith("ar"):
            request.update_context(lang="ar_001")
        elif normalized.startswith("en"):
            request.update_context(lang="en_US")

    def _json_body(self):
        if not request.httprequest.data:
            return {}
        try:
            return json.loads(request.httprequest.data.decode("utf-8"))
        except Exception:
            return {}

    def _args_int(self, key, default=0):
        value = request.httprequest.args.get(key)
        if value in (None, ""):
            return default
        try:
            return int(value)
        except Exception:
            return default

    def _args_float(self, key, default=0.0):
        value = request.httprequest.args.get(key)
        if value in (None, ""):
            return default
        try:
            return float(value)
        except Exception:
            return default

    def _args_bool(self, key, default=False):
        value = request.httprequest.args.get(key)
        if value in (None, ""):
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    def _payload_bool(self, payload, key, default=False):
        value = payload.get(key, default)
        if isinstance(value, bool):
            return value
        if value in (None, ""):
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    def _role_of(self, user):
        if user.has_group("ftiq_pharma_sfa.group_ftiq_manager"):
            return "manager"
        if user.has_group("ftiq_pharma_sfa.group_ftiq_supervisor"):
            return "supervisor"
        return "representative"

    def _current_user(self):
        return request.env.user

    def _current_role(self):
        return self._role_of(self._current_user())

    def _role_label(self, role):
        return {
            "manager": _("Manager"),
            "supervisor": _("Supervisor"),
            "representative": _("Representative"),
        }.get(role or "", _("Representative"))

    def _scope_users(self):
        user = self._current_user()
        teams_model = request.env["crm.team"]
        role = self._role_of(user)
        if role == "manager":
            teams = teams_model.search([("company_id", "=", user.company_id.id)])
            scope_users = (teams.mapped("member_ids") | teams.mapped("user_id") | user).filtered(
                lambda member: not member.share and member.company_id == user.company_id
            )
            return role, teams, scope_users
        if role == "supervisor":
            teams = teams_model.search([("user_id", "=", user.id)])
            scope_users = (teams.mapped("member_ids") | user).filtered(lambda member: not member.share)
            return role, teams, scope_users
        teams = user.sale_team_id if user.sale_team_id else teams_model
        return role, teams, user

    def _host_url(self):
        return request.httprequest.url_root.rstrip("/")

    def _client_request_metadata(self):
        forwarded_for = request.httprequest.headers.get("X-Forwarded-For", "")
        remote_ip = forwarded_for.split(",")[0].strip() or request.httprequest.remote_addr or ""
        user_agent = request.httprequest.headers.get("User-Agent", "") or ""
        return {
            "ip": remote_ip[:128],
            "user_agent": user_agent[:512],
        }

    def _request_database(self):
        for candidate in (
            request.httprequest.headers.get("X-Odoo-Database"),
            request.httprequest.headers.get("X-FTIQ-Database"),
            request.httprequest.args.get("db"),
        ):
            normalized = (candidate or "").strip()
            if normalized:
                return normalized
        return (request.session.db or request.db or "").strip()

    def _bearer_token(self):
        header_value = (request.httprequest.headers.get("Authorization") or "").strip()
        if not header_value.lower().startswith("bearer "):
            return ""
        return header_value[7:].strip()

    def _issue_session_cookie(self, db, uid):
        request.session.db = db
        request.session.uid = uid
        registry = odoo.modules.registry.Registry(db)
        with registry.cursor() as cr:
            env = api.Environment(cr, uid, request.session.context)
            odoo_http.root.session_store.rotate(request.session, env)
            request.future_response.set_cookie(
                "session_id",
                request.session.sid,
                max_age=odoo_http.get_session_max_inactivity(env),
                httponly=True,
                secure=request.httprequest.scheme == "https",
                samesite="Lax",
            )
        request.update_env(user=uid)

    def _mobile_request_uid(self, payload):
        value = ""
        if isinstance(payload, dict):
            value = payload.get("mobile_request_uid") or payload.get("request_uid") or ""
        return str(value).strip()[:128]

    def _mobile_request_log(self, request_uid):
        if not request_uid:
            return request.env["ftiq.mobile.request.log"]
        return request.env["ftiq.mobile.request.log"].search([
            ("request_uid", "=", request_uid),
            ("user_id", "=", self._current_user().id),
            ("company_id", "=", self._current_user().company_id.id),
            ("request_path", "=", request.httprequest.path),
        ], limit=1)

    def _replay_mobile_request(self, payload, serializer, *, detailed=True):
        request_uid = self._mobile_request_uid(payload)
        if not request_uid:
            return None
        request_log = self._mobile_request_log(request_uid)
        if not request_log:
            return None
        record = request.env[request_log.res_model].browse(request_log.res_id).exists()
        if not record:
            return self._error(
                _("The queued mobile request no longer points to an available record."),
                status=409,
                code="stale_mobile_request",
            )
        return self._ok(serializer(record, detailed=detailed))

    def _remember_mobile_request(self, payload, record):
        request_uid = self._mobile_request_uid(payload)
        if not request_uid or not record:
            return
        request_log = self._mobile_request_log(request_uid)
        if request_log:
            return
        request.env["ftiq.mobile.request.log"].create({
            "request_uid": request_uid,
            "request_path": request.httprequest.path,
            "user_id": self._current_user().id,
            "company_id": self._current_user().company_id.id,
            "res_model": record._name,
            "res_id": record.id,
        })

    def _image_url(self, model, record_id, field_name):
        if not record_id:
            return ""
        return f"{self._host_url()}/web/image/{model}/{record_id}/{field_name}"

    def _partner_client_type_label(self, partner):
        if not partner:
            return ""
        selection = dict(partner._fields["ftiq_client_type"].selection)
        client_type = getattr(partner, "ftiq_client_type", "") or ""
        return selection.get(client_type, _("Client")) if client_type else ""

    def _geo_context_from_payload(self, payload):
        return {
            "ftiq_latitude": payload.get("latitude"),
            "ftiq_longitude": payload.get("longitude"),
            "ftiq_accuracy": payload.get("accuracy", 0),
            "ftiq_is_mock": self._payload_bool(payload, "is_mock", False),
        }

    def _serialize_mobile_access(self, user=None):
        target_user = user or self._current_user()
        if not target_user:
            return {}
        try:
            user_record = request.env["res.users"].browse(target_user.id).exists()
        except (AccessError, AttributeError, ValueError):
            return {}
        if not user_record:
            return {}
        return user_record.get_ftiq_mobile_access_payload()

    def _current_mobile_access(self):
        cached = getattr(request, "_ftiq_mobile_access_payload", None)
        if cached is None:
            cached = self._serialize_mobile_access()
            request._ftiq_mobile_access_payload = cached
        return cached or {}

    def _mobile_permission(self, scope, key, default=False):
        payload = self._current_mobile_access()
        if not payload.get("enabled"):
            return False
        scope_map = {
            "navigation": "navigation",
            "workspace": "workspaces",
            "section": "sections",
            "action": "actions",
            "global_feature": "global_features",
        }
        bucket = payload.get(scope_map.get(scope, ""), {})
        if not isinstance(bucket, dict):
            return default
        if key not in bucket:
            return default
        return bool(bucket.get(key))

    def _ensure_mobile_permission(self, scope, key, operation):
        if self._mobile_permission(scope, key):
            return
        raise AccessError(_("You do not have permission to %s.") % operation)

    def _enabled_sections(self, *keys):
        return [
            key for key in keys
            if self._mobile_permission("section", key)
        ]

    def _ui_action_definition(self, action_key, variant):
        entry = MOBILE_CATALOG_BY_FULL_KEY.get("action.%s" % action_key)
        if not entry:
            return {}
        return {
            "key": action_key.split(".")[-1],
            "full_key": action_key,
            "variant": variant,
            "ui_order": entry["ui_order"],
        }

    def _build_ui_actions(self, *definitions):
        actions = []
        for action_key, enabled, variant in definitions:
            if not enabled:
                continue
            action = self._ui_action_definition(action_key, variant)
            if action:
                actions.append(action)
        return actions

    def _scope_domain(self, model_name):
        user = self._current_user()
        role = self._role_of(user)
        if model_name == "ftiq.field.attendance":
            if role == "manager":
                return []
            if role == "supervisor":
                return expression.OR([
                    [("user_id", "=", user.id)],
                    [("user_id.sale_team_id.user_id", "=", user.id)],
                ])
            return [("user_id", "=", user.id)]
        if model_name == "ftiq.visit":
            if role == "manager":
                return []
            if role == "supervisor":
                return expression.OR([
                    [("user_id", "=", user.id)],
                    [("team_id.user_id", "=", user.id)],
                ])
            return [("user_id", "=", user.id)]
        if model_name == "ftiq.weekly.plan":
            if role == "manager":
                return []
            if role == "supervisor":
                return expression.OR([
                    [("line_ids.user_id", "=", user.id)],
                    [("team_id.user_id", "=", user.id)],
                ])
            return [("line_ids.user_id", "=", user.id)]
        if model_name == "ftiq.weekly.plan.line":
            if role == "manager":
                return []
            if role == "supervisor":
                return expression.OR([
                    [("user_id", "=", user.id)],
                    [("team_id.user_id", "=", user.id)],
                ])
            return [("user_id", "=", user.id)]
        if model_name == "ftiq.daily.task":
            if role == "manager":
                return []
            if role == "supervisor":
                return expression.OR([
                    [("user_id", "=", user.id)],
                    [("team_id.user_id", "=", user.id)],
                ])
            return [("user_id", "=", user.id)]
        if model_name == "ftiq.visit.product.line":
            if role == "manager":
                return []
            if role == "supervisor":
                return expression.OR([
                    [("visit_id.user_id", "=", user.id)],
                    [("visit_id.team_id.user_id", "=", user.id)],
                ])
            return [("visit_id.user_id", "=", user.id)]
        if model_name == "ftiq.material.view.log":
            if role == "manager":
                return []
            if role == "supervisor":
                return expression.OR([
                    [("visit_id.user_id", "=", user.id)],
                    [("visit_id.team_id.user_id", "=", user.id)],
                ])
            return [("visit_id.user_id", "=", user.id)]
        if model_name == "ftiq.stock.check":
            if role == "manager":
                return []
            if role == "supervisor":
                return expression.OR([
                    [("user_id", "=", user.id)],
                    [("team_id.user_id", "=", user.id)],
                ])
            return [("user_id", "=", user.id)]
        if model_name == "sale.order":
            base = [("is_field_order", "=", True)]
            if role == "manager":
                return base
            if role == "supervisor":
                return expression.AND([
                    base,
                    expression.OR([
                        [("user_id", "=", user.id)],
                        [("user_id.sale_team_id.user_id", "=", user.id)],
                        [("ftiq_visit_id.team_id.user_id", "=", user.id)],
                    ]),
                ])
            return expression.AND([base, [("user_id", "=", user.id)]])
        if model_name == "purchase.order":
            base = [("company_id", "=", user.company_id.id)]
            if role == "manager":
                return base
            return expression.AND([
                base,
                expression.OR([
                    [("user_id", "=", user.id)],
                    [("create_uid", "=", user.id)],
                ]),
            ])
        if model_name == "project.task":
            base = [("company_id", "=", user.company_id.id)]
            if role == "manager":
                return base
            if role == "supervisor":
                return expression.AND([
                    base,
                    expression.OR([
                        [("user_ids", "in", [user.id])],
                        [("create_uid", "=", user.id)],
                        [("ftiq_daily_task_id.user_id", "=", user.id)],
                        [("ftiq_daily_task_id.team_id.user_id", "=", user.id)],
                        [("ftiq_plan_id.team_id.user_id", "=", user.id)],
                    ]),
                ])
            return expression.AND([
                base,
                expression.OR([
                    [("user_ids", "in", [user.id])],
                    [("create_uid", "=", user.id)],
                    [("ftiq_daily_task_id.user_id", "=", user.id)],
                ]),
            ])
        if model_name == "project.project":
            base = [("company_id", "=", user.company_id.id)]
            if role == "manager":
                return base
            if role == "supervisor":
                return expression.AND([
                    base,
                    expression.OR([
                        [("user_id", "=", user.id)],
                        [("favorite_user_ids", "in", [user.id])],
                        [("task_ids.user_ids", "in", [user.id])],
                        [("task_ids.ftiq_daily_task_id.user_id", "=", user.id)],
                        [("task_ids.ftiq_daily_task_id.team_id.user_id", "=", user.id)],
                        [("ftiq_plan_ids.team_id.user_id", "=", user.id)],
                        [("ftiq_plan_ids.line_ids.user_id", "=", user.id)],
                    ]),
                ])
            return expression.AND([
                base,
                expression.OR([
                    [("user_id", "=", user.id)],
                    [("favorite_user_ids", "in", [user.id])],
                    [("task_ids.user_ids", "in", [user.id])],
                    [("task_ids.ftiq_daily_task_id.user_id", "=", user.id)],
                    [("ftiq_plan_ids.line_ids.user_id", "=", user.id)],
                ]),
            ])
        if model_name == "account.payment":
            base = [("is_field_collection", "=", True)]
            if role == "manager":
                return base
            if role == "supervisor":
                return expression.AND([
                    base,
                    expression.OR([
                        [("ftiq_user_id", "=", user.id)],
                        [("ftiq_team_id.user_id", "=", user.id)],
                    ]),
                ])
            return expression.AND([base, [("ftiq_user_id", "=", user.id)]])
        if model_name == "ftiq.collection.line":
            if role == "manager":
                return []
            if role == "supervisor":
                return expression.OR([
                    [("payment_id.ftiq_user_id", "=", user.id)],
                    [("payment_id.ftiq_team_id.user_id", "=", user.id)],
                ])
            return [("payment_id.ftiq_user_id", "=", user.id)]
        if model_name == "account.move":
            base = [
                ("is_field_invoice", "=", True),
            ]
            if role == "manager":
                return base
            if role == "supervisor":
                return expression.AND([
                    base,
                    expression.OR([
                        [("ftiq_access_user_id", "=", user.id)],
                        [("ftiq_team_id.user_id", "=", user.id)],
                    ]),
                ])
            return expression.AND([
                base,
                [("ftiq_access_user_id", "=", user.id)],
            ])
        if model_name == "hr.expense":
            base = [("is_field_expense", "=", True)]
            if role == "manager":
                return base
            if role == "supervisor":
                return expression.AND([
                    base,
                    expression.OR([
                        [("ftiq_user_id", "=", user.id)],
                        [("employee_id.user_id", "=", user.id)],
                        [("ftiq_team_id.user_id", "=", user.id)],
                    ]),
                ])
            return expression.AND([
                base,
                expression.OR([
                    [("ftiq_user_id", "=", user.id)],
                    [("employee_id.user_id", "=", user.id)],
                ]),
            ])
        if model_name == "ftiq.team.message":
            base = [("company_id", "=", user.company_id.id)]
            if role == "manager":
                return base
            if role == "supervisor":
                return expression.AND([
                    base,
                    expression.OR([
                        [("author_id", "=", user.id)],
                        [("target_user_id", "=", user.id)],
                        [("team_id.user_id", "=", user.id)],
                    ]),
                ])
            return expression.AND([
                base,
                expression.OR([
                    [("target_user_id", "=", user.id)],
                    expression.AND([
                        [("is_team_wide", "=", True)],
                        [("team_id.member_ids", "in", [user.id])],
                    ]),
                ]),
            ])
        if model_name == "ftiq.mobile.device":
            if role == "manager":
                return [("company_id", "=", user.company_id.id)]
            if role == "supervisor":
                return expression.AND([
                    [("company_id", "=", user.company_id.id)],
                    expression.OR([
                        [("user_id", "=", user.id)],
                        [("team_id.user_id", "=", user.id)],
                    ]),
                ])
            return [("user_id", "=", user.id)]
        if model_name == "ftiq.mobile.notification":
            return [
                ("company_id", "=", user.company_id.id),
                ("user_id", "=", user.id),
            ]
        if model_name == "mail.activity":
            return [
                ("user_id", "=", user.id),
                ("active", "=", True),
            ]
        if model_name == "ftiq.mobile.runtime.policy":
            return [("company_id", "=", user.company_id.id)]
        return []

    def _search_scoped(self, model_name, domain=None, order=None, limit=None):
        model = request.env[model_name]
        try:
            if not model.check_access_rights("read", raise_exception=False):
                return model.browse()
        except (AccessError, ValueError):
            return model.browse()
        final_domain = expression.AND([self._scope_domain(model_name), domain or []])
        return model.search(final_domain, order=order, limit=limit)

    def _browse_scoped(self, model_name, record_id):
        return self._search_scoped(model_name, [("id", "=", record_id)], limit=1)[:1]

    def _safe_scoped_record(self, model_name, record):
        if not record:
            return request.env[model_name]
        if getattr(record, "_name", model_name) != model_name:
            return request.env[model_name]
        try:
            if len(record) > 1:
                record = record[:1]
        except Exception:
            return request.env[model_name]
        try:
            record_id = record.id
        except (AccessError, AttributeError, ValueError):
            return request.env[model_name]
        if not record_id:
            return request.env[model_name]
        try:
            scoped_record = self._browse_scoped(model_name, record_id).exists()
        except AccessError:
            return request.env[model_name]
        if not scoped_record:
            return request.env[model_name]
        try:
            if not scoped_record.check_access_rights("read", raise_exception=False):
                return request.env[model_name]
        except (AccessError, ValueError):
            return request.env[model_name]
        return scoped_record

    def _safe_scoped_id(self, model_name, record):
        scoped_record = self._safe_scoped_record(model_name, record)
        return scoped_record.id if scoped_record else False

    def _safe_related_record(self, record, field_name, model_name):
        if not record:
            return request.env[model_name]
        if field_name not in getattr(record, "_fields", {}):
            return request.env[model_name]
        try:
            related_record = getattr(record, field_name)
        except (AccessError, AttributeError):
            return request.env[model_name]
        return self._safe_scoped_record(model_name, related_record)

    def _safe_related_scoped_id(self, record, field_name, model_name):
        scoped_record = self._safe_related_record(record, field_name, model_name)
        return scoped_record.id if scoped_record else False

    def _is_thread_supported_model(self, model_name):
        return (model_name or "").strip() in self._THREAD_SUPPORTED_MODELS

    def _browse_thread_record(self, model_name, record_id):
        if not self._is_thread_supported_model(model_name):
            return request.env[model_name]
        return self._browse_scoped(model_name, record_id).exists()

    def _record_has_access(self, record, mode):
        if not record:
            return False
        try:
            if not record.check_access_rights(mode, raise_exception=False):
                return False
        except (AccessError, ValueError):
            return False
        return True

    def _thread_attachments_for_record(self, record):
        message_ids = request.env["mail.message"].search(
            [
                ("model", "=", record._name),
                ("res_id", "=", record.id),
            ]
        ).ids
        domain = expression.OR([
            [
                ("res_model", "=", record._name),
                ("res_id", "=", record.id),
                ("type", "=", "binary"),
            ],
            [
                ("res_model", "=", "mail.message"),
                ("res_id", "in", message_ids or [0]),
                ("type", "=", "binary"),
            ],
        ])
        return request.env["ir.attachment"].sudo().search(
            domain,
            order="create_date desc, id desc",
        )

    def _thread_followers_for_record(self, record):
        if "message_partner_ids" not in getattr(record, "_fields", {}):
            return request.env["res.partner"]
        try:
            followers = record.message_partner_ids
        except AccessError:
            return request.env["res.partner"]
        visible_followers = request.env["res.partner"]
        for partner in followers:
            scoped_partner = self._safe_scoped_record("res.partner", partner)
            if scoped_partner:
                visible_followers |= scoped_partner
        return visible_followers

    def _serialize_thread_attachment(self, attachment):
        mimetype = (attachment.mimetype or "").strip()
        return {
            "id": attachment.id,
            "name": attachment.name or attachment.display_name or "",
            "mimetype": mimetype,
            "file_size": attachment.file_size or 0,
            "is_image": mimetype.startswith("image/"),
            "url": f"{self._host_url()}/web/content/{attachment.id}?download=true",
            "preview_url": self._image_url("ir.attachment", attachment.id, "datas")
            if mimetype.startswith("image/")
            else "",
            "create_date": fields.Datetime.to_string(attachment.create_date)
            if attachment.create_date
            else None,
            "author": self._serialize_user(attachment.create_uid)
            if attachment.create_uid
            else {},
        }

    def _serialize_thread_follower(self, partner):
        user = self._safe_scoped_record("res.users", partner.user_ids[:1])
        return {
            "partner_id": partner.id,
            "user_id": user.id if user else False,
            "name": partner.display_name,
            "email": partner.email or "",
            "phone": partner.phone or partner.mobile or "",
            "image_url": self._image_url("res.partner", partner.id, "avatar_128"),
        }

    def _thread_notification_domain(self, record, message_ids=None):
        domain = [
            ("res_partner_id", "=", self._current_user().partner_id.id),
            ("notification_type", "=", "inbox"),
            ("mail_message_id.model", "=", record._name),
            ("mail_message_id.res_id", "=", record.id),
        ]
        if message_ids:
            domain.append(("mail_message_id", "in", list(message_ids)))
        return domain

    def _mark_thread_read_notifications(self, record, message_ids=None):
        notifications = request.env["mail.notification"].search(
            expression.AND(
                [
                    self._thread_notification_domain(record, message_ids=message_ids),
                    [("is_read", "=", False)],
                ]
            )
        )
        if notifications:
            notifications.write({"is_read": True})
        return notifications

    def _serialize_thread_author(self, message):
        partner = self._safe_related_record(message, "author_id", "res.partner")
        sudo_partner = request.env["res.partner"]
        try:
            sudo_partner = message.sudo().author_id
        except AccessError:
            sudo_partner = request.env["res.partner"]
        user_source = partner or sudo_partner
        user = (
            self._safe_scoped_record("res.users", user_source.user_ids[:1])
            if user_source
            else request.env["res.users"]
        )
        author_name = ""
        if partner:
            author_name = partner.display_name
        elif sudo_partner:
            author_name = sudo_partner.display_name or ""
        if not author_name:
            try:
                author_name = message.email_from or ""
            except AccessError:
                author_name = ""
        if not author_name:
            author_name = _("System")
        return {
            "user_id": user.id if user else False,
            "partner_id": partner.id if partner else False,
            "name": author_name,
        }

    def _serialize_thread_message(self, message, notification_map=None):
        notification = (notification_map or {}).get(message.id)
        body = html2plaintext(message.body or "").strip()
        return {
            "id": message.id,
            "subject": message.subject or "",
            "body": body,
            "preview": (message.preview or body)[:280],
            "message_type": message.message_type or "",
            "subtype": {
                "id": message.subtype_id.id if message.subtype_id else False,
                "name": message.subtype_id.display_name if message.subtype_id else "",
            },
            "author": self._serialize_thread_author(message),
            "date": fields.Datetime.to_string(message.date) if message.date else None,
            "is_read": bool(notification.is_read) if notification else True,
            "notification_id": notification.id if notification else False,
        }

    def _serialize_thread_record(self, record):
        partner = request.env["res.partner"]
        if "partner_id" in record._fields:
            partner = self._safe_related_record(record, "partner_id", "res.partner")
        user = request.env["res.users"]
        for field_name in ("user_id", "ftiq_user_id", "ftiq_access_user_id", "supervisor_id", "create_uid"):
            user = self._safe_related_record(record, field_name, "res.users")
            if user:
                break
        if not user and "user_ids" in record._fields:
            try:
                for candidate in record.user_ids:
                    scoped_candidate = self._safe_scoped_record("res.users", candidate)
                    if scoped_candidate:
                        user = scoped_candidate
                        break
            except AccessError:
                user = request.env["res.users"]
        if not user and "team_id" in record._fields:
            team = self._safe_related_record(record, "team_id", "crm.team")
            if team and team.user_id:
                user = self._safe_scoped_record("res.users", team.user_id)
        try:
            record_name = record.display_name or ""
        except AccessError:
            record_name = ""
        if not record_name:
            record_name = f"{record._description or record._name} #{record.id}"
        state = ""
        if "state" in record._fields:
            try:
                state = getattr(record, "state", "") or ""
            except AccessError:
                state = ""
        date_value = ""
        for field_name in (
            "scheduled_date",
            "visit_date",
            "week_start",
            "date_order",
            "invoice_date",
            "date_start",
            "date",
            "date_deadline",
        ):
            if field_name not in record._fields:
                continue
            try:
                value = getattr(record, field_name, False)
            except AccessError:
                value = False
            if value:
                date_value = str(value)
                break
        can_write = self._record_has_access(record, "write")
        can_post_message = bool(
            can_write and self._mobile_permission("action", "thread.post_message")
        )
        can_upload_attachment = bool(
            can_write and self._mobile_permission("action", "thread.upload_attachment")
        )
        return {
            "model": record._name,
            "id": record.id,
            "name": record_name,
            "state": state,
            "date": date_value,
            "partner": self._serialize_partner_card(partner) if partner else {},
            "user": self._serialize_user(user) if user else {},
            "available_actions": {
                "post_message": can_post_message,
                "upload_attachment": can_upload_attachment,
            },
            "ui_actions": self._build_ui_actions(
                ("thread.post_message", can_post_message, "primary"),
                ("thread.upload_attachment", can_upload_attachment, "secondary"),
            ),
        }

    def _serialize_thread_feed(self, record, limit=40):
        messages = request.env["mail.message"].search(
            [
                ("model", "=", record._name),
                ("res_id", "=", record.id),
                ("message_type", "!=", "user_notification"),
            ],
            order="id desc",
            limit=limit,
        )
        ordered_messages = messages.sorted(key=lambda message: message.id)
        notifications = request.env["mail.notification"].sudo().search(
            self._thread_notification_domain(record, message_ids=ordered_messages.ids)
        )
        notification_map = {
            notification.mail_message_id.id: notification for notification in notifications
        }
        unread_count = len(
            [notification for notification in notifications if not notification.is_read]
        )
        attachments = self._thread_attachments_for_record(record)
        followers = self._thread_followers_for_record(record)
        return {
            "record": self._serialize_thread_record(record),
            "current_user_id": self._current_user().id,
            "visible_sections": self._enabled_sections(
                "thread.messages",
                "thread.attachments",
                "thread.followers",
            ),
            "ui_actions": self._build_ui_actions(
                (
                    "thread.post_message",
                    self._mobile_permission("action", "thread.post_message"),
                    "primary",
                ),
                (
                    "thread.upload_attachment",
                    self._mobile_permission("action", "thread.upload_attachment"),
                    "secondary",
                ),
            ),
            "messages": [
                self._serialize_thread_message(message, notification_map=notification_map)
                for message in ordered_messages
            ],
            "unread_count": unread_count,
            "attachments": [
                self._serialize_thread_attachment(attachment)
                for attachment in attachments
            ],
            "attachment_count": len(attachments),
            "followers": [
                self._serialize_thread_follower(partner)
                for partner in followers
            ],
            "follower_count": len(followers),
        }

    def _message_deep_link(self, message, task_record=None):
        return f"ftiq://team-message?id={message.id}"

    def _notification_summary(self, sync_live=False):
        if sync_live:
            self._sync_live_activity_notifications()
        unread_domain = [("is_read", "=", False)]
        return {
            "unread_count": self._search_scoped(
                "ftiq.mobile.notification",
                unread_domain,
            ).__len__(),
            "total_count": self._search_scoped(
                "ftiq.mobile.notification",
            ).__len__(),
        }

    def _owner_field_for(self, record_or_model):
        model_name = record_or_model if isinstance(record_or_model, str) else getattr(record_or_model, "_name", "")
        return self._OWNER_FIELD_BY_MODEL.get(model_name)

    def _sync_live_activity_notifications(self):
        notification_model = request.env["ftiq.mobile.notification"].with_context(
            ftiq_skip_push_dispatch=True
        )
        current_user = self._current_user()
        for sync_method, sync_name in (
            (notification_model.sync_live_activities_for_user, "activities"),
            (notification_model.sync_live_mail_notifications_for_user, "mail_notifications"),
        ):
            try:
                sync_method(current_user)
            except Exception:
                _logger.exception(
                    "FTIQ mobile live notification sync failed: %s",
                    sync_name,
                )

    def _record_owner(self, record):
        field_name = self._owner_field_for(record)
        if not field_name or not record:
            return request.env["res.users"]
        return getattr(record, field_name, request.env["res.users"])

    def _is_current_user_owner(self, record):
        if not record:
            return False
        owner = self._record_owner(record)
        current_user = self._current_user()
        return bool(owner and owner.id == current_user.id)

    def _ensure_current_user_owns(self, record, operation):
        if not record or self._is_current_user_owner(record):
            return
        raise AccessError(_("You cannot %s for another user.") % operation)

    def _ensure_role(self, allowed_roles, operation):
        role = self._current_role()
        if role in allowed_roles:
            return
        raise AccessError(_("You do not have permission to %s.") % operation)

    def _browse_mobile_client(self, partner_id):
        domain = expression.AND([
            request.env["ftiq.plan.candidate.service"].get_client_base_domain(),
            [("id", "=", partner_id)],
        ])
        return request.env["res.partner"].search(domain, limit=1)

    def _serialize_company(self, company):
        return {
            "id": company.id,
            "name": company.display_name,
            "currency": {
                "id": company.currency_id.id,
                "name": company.currency_id.name,
                "symbol": company.currency_id.symbol,
            },
        }

    def _current_mobile_runtime_policy(self):
        return request.env["ftiq.mobile.runtime.policy"].search(
            [("company_id", "=", self._current_user().company_id.id)],
            limit=1,
        )

    def _current_mobile_device(self, installation_id):
        normalized_installation_id = (installation_id or "").strip()
        if not normalized_installation_id:
            return request.env["ftiq.mobile.device"]
        return request.env["ftiq.mobile.device"].search(
            [
                ("user_id", "=", self._current_user().id),
                ("installation_id", "=", normalized_installation_id),
            ],
            limit=1,
        )

    def _serialize_mobile_device(self, device):
        if not device:
            return {}
        return {
            "id": device.id,
            "name": device.name,
            "installation_id": device.installation_id,
            "platform": device.platform,
            "state": device.state,
            "app_version": device.app_version or "",
            "build_number": device.build_number or "",
            "locale_code": device.locale_code or "",
            "device_name": device.device_name or "",
            "device_model": device.device_model or "",
            "device_brand": device.device_brand or "",
            "device_manufacturer": device.device_manufacturer or "",
            "os_version": device.os_version or "",
            "notification_permission": bool(device.notification_permission),
            "location_permission": device.location_permission or "",
            "location_services_enabled": bool(device.location_services_enabled),
            "biometrics_available": bool(device.biometrics_available),
            "last_seen_at": fields.Datetime.to_string(device.last_seen_at) if device.last_seen_at else None,
            "last_login_at": fields.Datetime.to_string(device.last_login_at) if device.last_login_at else None,
            "session_state": device.session_token_state(),
            "session_token_issued_at": fields.Datetime.to_string(device.session_token_issued_at)
            if device.session_token_issued_at
            else None,
            "session_token_last_seen_at": fields.Datetime.to_string(device.session_token_last_seen_at)
            if device.session_token_last_seen_at
            else None,
            "session_token_expires_at": fields.Datetime.to_string(device.session_token_expires_at)
            if device.session_token_expires_at
            else None,
            "is_current": False,
        }

    def _serialize_mobile_runtime(self, policy=None, platform="", app_version="", build_number="", device=False):
        current_policy = policy or self._current_mobile_runtime_policy()
        if current_policy:
            data = current_policy.evaluate_client(
                platform=platform,
                app_version=app_version,
                build_number=build_number,
                device=device,
            )
        else:
            normalized_platform = (platform or "").strip().lower() or "android"
            data = {
                "policy_id": False,
                "platform": "ios" if normalized_platform == "ios" else "android",
                "current_version": (app_version or "").strip(),
                "build_number": (build_number or "").strip(),
                "min_version": "",
                "recommended_version": "",
                "latest_version": "",
                "store_url": "",
                "force_update": False,
                "registration_required": False,
                "maintenance_enabled": False,
                "maintenance_message": "",
                "update_available": False,
                "update_required": False,
                "allowed": device.state != "revoked" if device else True,
                "reason": "device_revoked" if device and device.state == "revoked" else "ok",
                "message": _("This device has been revoked. Contact your administrator.")
                if device and device.state == "revoked"
                else "",
                "device_registered": bool(device),
                "device_state": device.state if device else "unregistered",
            }
        data["device"] = self._serialize_mobile_device(device)
        return data

    def _serialize_user(self, user):
        user = self._safe_scoped_record("res.users", user)
        if not user:
            return {}
        partner = self._safe_related_record(user, "partner_id", "res.partner")
        return {
            "id": user.id,
            "name": user.display_name,
            "login": user.login,
            "role": self._role_of(user),
            "role_label": self._role_label(self._role_of(user)),
            "email": user.email or (partner.email if partner else "") or "",
            "phone": partner.phone if partner else "",
            "mobile": partner.mobile if partner else "",
            "image_url": self._image_url("res.users", user.id, "avatar_128"),
            "team": {
                "id": user.sale_team_id.id if user.sale_team_id else False,
                "name": user.sale_team_id.display_name if user.sale_team_id else "",
            },
            "area": {
                "id": user.ftiq_area_id.id if getattr(user, "ftiq_area_id", False) else False,
                "name": user.ftiq_area_id.name if getattr(user, "ftiq_area_id", False) else "",
            },
            "company": self._serialize_company(user.company_id),
        }

    def _serialize_attendance(self, attendance):
        if not attendance:
            return {}
        can_check_out = bool(
            attendance.state == "checked_in"
            and self._mobile_permission("workspace", "attendance")
        )
        return {
            "id": attendance.id,
            "name": attendance.display_name,
            "state": attendance.state,
            "date": str(attendance.date or ""),
            "check_in_time": fields.Datetime.to_string(attendance.check_in_time) if attendance.check_in_time else None,
            "check_out_time": fields.Datetime.to_string(attendance.check_out_time) if attendance.check_out_time else None,
            "working_hours": attendance.working_hours,
            "visit_count": attendance.visit_count,
            "check_in": {
                "latitude": attendance.check_in_latitude,
                "longitude": attendance.check_in_longitude,
                "accuracy": attendance.check_in_accuracy,
                "is_mock": attendance.check_in_is_mock,
            },
            "check_out": {
                "latitude": attendance.check_out_latitude,
                "longitude": attendance.check_out_longitude,
                "accuracy": attendance.check_out_accuracy,
                "is_mock": attendance.check_out_is_mock,
            },
            "available_actions": {
                "check_out": can_check_out,
            },
            "ui_actions": [],
        }

    def _serialize_partner_card(self, partner):
        return {
            "id": partner.id,
            "name": partner.display_name,
            "client_code": partner.ftiq_client_code or "",
            "client_type": partner.ftiq_client_type or "client",
            "client_type_label": self._partner_client_type_label(partner),
            "city": partner.ftiq_city_id.name or partner.city or "",
            "area": partner.ftiq_area_id.name or "",
            "specialty": partner.ftiq_specialty_id.name or "",
            "classification": partner.ftiq_classification_id.name or "",
            "category": partner.ftiq_client_category_id.name or "",
            "phone": partner.phone or "",
            "mobile": partner.mobile or "",
            "address": partner.ftiq_execution_address or "",
            "geo_confirmed": bool(partner.ftiq_geo_confirmed),
            "latitude": partner.partner_latitude or 0.0,
            "longitude": partner.partner_longitude or 0.0,
            "counters": {
                "visits": partner.ftiq_total_visits,
                "orders": partner.ftiq_order_count,
                "collections": partner.ftiq_collection_count,
                "invoices": partner.ftiq_invoice_count,
            },
            "open_invoice_amount": getattr(partner, "ftiq_open_invoice_amount", 0.0),
            "image_url": self._image_url("res.partner", partner.id, "avatar_128"),
        }

    def _serialize_visit(self, visit, detailed=False):
        is_owner = self._is_current_user_owner(visit)
        can_review = self._current_role() in {"supervisor", "manager"}
        can_edit = bool(
            is_owner
            and visit.state in ("draft", "in_progress", "returned")
            and self._mobile_permission("action", "visit.edit")
        )
        can_start = bool(
            is_owner
            and visit.state == "draft"
            and self._mobile_permission("action", "visit.start")
        )
        can_end = bool(
            is_owner
            and visit.state == "in_progress"
            and self._mobile_permission("action", "visit.end")
        )
        can_submit = bool(
            is_owner
            and visit.state in ("in_progress", "returned")
            and self._mobile_permission("action", "visit.submit")
        )
        can_approve = bool(
            visit.state == "submitted"
            and can_review
            and self._mobile_permission("action", "visit.approve")
        )
        can_return = bool(
            visit.state == "submitted"
            and can_review
            and self._mobile_permission("action", "visit.return")
        )
        can_create_order = bool(
            is_owner
            and visit.state == "in_progress"
            and self._mobile_permission("action", "visit.create_order")
        )
        can_create_collection = bool(
            is_owner
            and visit.state == "in_progress"
            and self._mobile_permission("action", "visit.create_collection")
        )
        can_create_stock_check = bool(
            is_owner
            and visit.state == "in_progress"
            and self._mobile_permission("action", "visit.create_stock_check")
        )
        data = {
            "id": visit.id,
            "name": visit.display_name,
            "state": visit.state,
            "visit_date": str(visit.visit_date or ""),
            "partner": self._serialize_partner_card(visit.partner_id),
            "user": {
                "id": visit.user_id.id,
                "name": visit.user_id.display_name,
            },
            "is_planned": visit.is_planned,
            "duration": visit.duration,
            "outcome": visit.outcome or "",
            "general_feedback": visit.general_feedback or "",
            "unplanned_reason": visit.unplanned_reason or "",
            "start_time": fields.Datetime.to_string(visit.start_time) if visit.start_time else None,
            "end_time": fields.Datetime.to_string(visit.end_time) if visit.end_time else None,
            "start_geo": {
                "latitude": visit.start_latitude,
                "longitude": visit.start_longitude,
                "accuracy": visit.start_accuracy,
            },
            "end_geo": {
                "latitude": visit.end_latitude,
                "longitude": visit.end_longitude,
                "accuracy": visit.end_accuracy,
            },
            "counts": {
                "product_lines": visit.detail_line_count,
                "material_logs": visit.material_log_count,
                "samples_distributed": visit.total_samples_distributed,
                "orders": visit.sale_order_count,
                "collections": visit.payment_count,
                "invoices": visit.invoice_count,
                "stock_checks": visit.stock_check_count,
            },
            "linked_records": {
                "attendance_id": visit.attendance_id.id if visit.attendance_id else False,
                "plan_line_id": visit.plan_line_id.id if visit.plan_line_id else False,
            },
            "visible_sections": self._enabled_sections(
                "visit.evidence",
                "visit.related_records",
                "visit.thread",
                "visit.activities",
            ),
            "available_actions": {
                "edit": can_edit,
                "start": can_start,
                "end": can_end,
                "submit": can_submit,
                "approve": can_approve,
                "return": can_return,
                "create_order": can_create_order,
                "create_collection": can_create_collection,
                "create_stock_check": can_create_stock_check,
            },
            "ui_actions": self._build_ui_actions(
                ("visit.start", can_start, "primary"),
                ("visit.end", can_end, "primary"),
                ("visit.submit", can_submit, "primary"),
                ("visit.approve", can_approve, "primary"),
                ("visit.edit", can_edit, "secondary"),
                ("visit.return", can_return, "destructive"),
                ("visit.create_order", can_create_order, "secondary"),
                ("visit.create_collection", can_create_collection, "secondary"),
                ("visit.create_stock_check", can_create_stock_check, "secondary"),
            ),
        }
        if detailed:
            data["product_lines"] = [{
                "id": line.id,
                "product_id": line.product_id.id,
                "product_name": line.product_id.display_name,
                "product": self._serialize_product(line.product_id),
                "call_reason_id": line.call_reason_id.id if line.call_reason_id else False,
                "call_reason_name": line.call_reason_id.name or "",
                "detail_notes": line.detail_notes or "",
                "outcome": line.outcome or "",
                "samples_distributed": line.samples_distributed,
                "stock_on_hand": line.stock_on_hand,
                "feedback": line.feedback or "",
                "sequence": line.sequence,
            } for line in visit.product_line_ids.sorted(key=lambda line: (line.sequence, line.id))]
            data["material_logs"] = [{
                "id": log.id,
                "material_id": log.material_id.id,
                "material_name": log.material_id.display_name,
                "material_type": log.material_type,
                "material_scope": log.material_scope,
                "product_id": log.product_id.id if log.product_id else False,
                "product_name": log.product_id.display_name if log.product_id else "",
                "product_line_id": log.product_line_id.id if log.product_line_id else False,
                "start_time": fields.Datetime.to_string(log.start_time) if log.start_time else None,
                "end_time": fields.Datetime.to_string(log.end_time) if log.end_time else None,
                "duration": log.duration,
                "note": log.note or "",
            } for log in visit.material_view_log_ids.sorted(key=lambda item: ((item.start_time or fields.Datetime.now()), item.id))]
            data["attachments"] = {
                "photo_1_url": self._image_url("ftiq.visit", visit.id, "photo_1") if visit.photo_1 else "",
                "photo_2_url": self._image_url("ftiq.visit", visit.id, "photo_2") if visit.photo_2 else "",
                "photo_3_url": self._image_url("ftiq.visit", visit.id, "photo_3") if visit.photo_3 else "",
                "signature_url": self._image_url("ftiq.visit", visit.id, "signature") if visit.signature else "",
            }
            data["linked_orders"] = [self._serialize_order(order) for order in visit.sale_order_ids]
            data["linked_collections"] = [self._serialize_collection(payment) for payment in visit.payment_ids]
            data["linked_stock_checks"] = [self._serialize_stock_check(check) for check in visit.stock_check_ids]
            data["activities"] = self._serialize_activities_for_record(visit)
        return data

    def _serialize_plan(self, plan, detailed=False):
        data = {
            "id": plan.id,
            "name": plan.display_name,
            "state": plan.state,
            "week_start": str(plan.week_start or ""),
            "week_end": str(plan.week_end or ""),
            "team": {
                "id": plan.team_id.id if plan.team_id else False,
                "name": plan.team_id.display_name if plan.team_id else "",
            },
            "supervisor": {
                "id": plan.supervisor_id.id if plan.supervisor_id else False,
                "name": plan.supervisor_id.display_name if plan.supervisor_id else "",
            },
            "stats": {
                "planned": plan.planned_count,
                "completed": plan.completed_count,
                "missed": plan.missed_count,
                "compliance_rate": plan.compliance_rate,
            },
            "note": plan.note or "",
        }
        if detailed:
            data["lines"] = [{
                "id": line.id,
                "state": line.state,
                "scheduled_date": str(line.scheduled_date or ""),
                "day_of_week": line.day_of_week or "",
                "partner": self._serialize_partner_card(line.partner_id),
                "user": {
                    "id": line.user_id.id if line.user_id else False,
                    "name": line.user_id.display_name if line.user_id else "",
                },
                "note": line.note or "",
                "visit_id": line.visit_id.id if line.visit_id else False,
                "task_id": self._safe_related_scoped_id(
                    line,
                    "daily_task_id",
                    "ftiq.daily.task",
                ),
            } for line in plan.line_ids.sorted(key=lambda item: ((item.scheduled_date or fields.Date.today()), item.sequence, item.id))]
        return data

    def _serialize_task(self, task, detailed=False):
        is_owner = self._is_current_user_owner(task)
        role = self._current_role()
        can_edit = bool(
            is_owner
            and task.state in ("draft", "pending", "in_progress", "returned")
            and self._mobile_permission("action", "task.edit")
        )
        can_start = bool(
            is_owner
            and task.state in ("draft", "pending", "returned")
            and self._mobile_permission("action", "task.start")
        )
        can_complete = bool(
            is_owner
            and task.state == "in_progress"
            and self._mobile_permission("action", "task.complete")
        )
        can_submit = bool(
            is_owner
            and task.state in ("in_progress", "completed", "returned")
            and task.confirmation_required
            and self._mobile_permission("action", "task.submit")
        )
        can_confirm = bool(
            task.state == "submitted"
            and role in {"supervisor", "manager"}
            and self._mobile_permission("action", "task.confirm")
        )
        can_return = bool(
            task.state == "submitted"
            and role in {"supervisor", "manager"}
            and self._mobile_permission("action", "task.return")
        )
        data = {
            "id": task.id,
            "name": task.display_name,
            "state": task.state,
            "task_type": task.task_type,
            "task_profile": {
                "id": task.task_profile_id.id if getattr(task, "task_profile_id", False) else False,
                "name": task.task_profile_id.display_name if getattr(task, "task_profile_id", False) else "",
            },
            "scheduled_date": fields.Datetime.to_string(task.scheduled_date) if task.scheduled_date else None,
            "completed_date": fields.Datetime.to_string(task.completed_date) if task.completed_date else None,
            "priority": task.priority,
            "description": task.description or "",
            "outcome": task.outcome or "",
            "profile_rules": {
                "requires_photos": bool(getattr(task, "requires_photos", False)),
                "required_photo_count": getattr(task, "required_photo_count", 0) or 0,
                "confirmation_required": bool(getattr(task, "confirmation_required", False)),
                "allow_manual_completion": bool(getattr(task, "allow_manual_completion", False)),
            },
            "partner": self._serialize_partner_card(task.partner_id) if task.partner_id else {},
            "user": {
                "id": task.user_id.id if task.user_id else False,
                "name": task.user_id.display_name if task.user_id else "",
                "phone": task.user_id.partner_id.phone if task.user_id and task.user_id.partner_id else "",
                "mobile": task.user_id.partner_id.mobile if task.user_id and task.user_id.partner_id else "",
            },
            "attachments": {
                "photo_1_url": self._image_url("ftiq.daily.task", task.id, "photo_1") if task.photo_1 else "",
                "photo_2_url": self._image_url("ftiq.daily.task", task.id, "photo_2") if task.photo_2 else "",
                "photo_3_url": self._image_url("ftiq.daily.task", task.id, "photo_3") if task.photo_3 else "",
            },
            "linked_records": {
                "visit_id": task.visit_id.id if task.visit_id else False,
                "sale_order_id": task.sale_order_id.id if task.sale_order_id else False,
                "payment_id": task.payment_id.id if task.payment_id else False,
                "stock_check_id": task.stock_check_id.id if task.stock_check_id else False,
                "project_task_id": self._safe_related_scoped_id(
                    task,
                    "project_task_id",
                    "project.task",
                ),
            },
            "visible_sections": self._enabled_sections(
                "task.evidence",
                "task.thread",
                "task.activities",
            ),
            "available_actions": {
                "edit": can_edit,
                "start": can_start,
                "complete": can_complete,
                "submit": can_submit,
                "confirm": can_confirm,
                "return": can_return,
            },
            "ui_actions": self._build_ui_actions(
                ("task.start", can_start, "primary"),
                ("task.complete", can_complete, "primary"),
                ("task.submit", can_submit, "primary"),
                ("task.confirm", can_confirm, "primary"),
                ("task.edit", can_edit, "secondary"),
                ("task.return", can_return, "destructive"),
            ),
        }
        if detailed:
            data["activities"] = self._serialize_activities_for_record(task)
        return data

    def _serialize_project(self, project, detailed=False):
        manager = self._safe_related_record(project, "user_id", "res.users")
        partner = self._safe_related_record(project, "partner_id", "res.partner")
        company = self._safe_related_record(project, "company_id", "res.company")
        next_milestone = getattr(project, "next_milestone_id", request.env["project.milestone"])
        data = {
            "id": project.id,
            "name": project.display_name,
            "description": html2plaintext(project.description or "").strip(),
            "partner": self._serialize_partner_card(partner) if partner else {},
            "company": self._serialize_company(company) if company else {},
            "manager": self._serialize_user(manager) if manager else {},
            "privacy_visibility": project.privacy_visibility or "",
            "date_start": str(project.date_start or ""),
            "date_end": str(project.date or ""),
            "task_count": project.task_count,
            "open_task_count": project.open_task_count,
            "closed_task_count": project.closed_task_count,
            "task_completion_percentage": project.task_completion_percentage,
            "milestone_count": getattr(project, "milestone_count", 0) or 0,
            "milestone_progress": getattr(project, "milestone_progress", 0) or 0,
            "update_count": getattr(project, "update_count", 0) or 0,
            "last_update_status": getattr(project, "last_update_status", "") or "",
            "next_milestone": {
                "id": next_milestone.id if next_milestone else False,
                "name": next_milestone.display_name if next_milestone else "",
                "deadline": str(next_milestone.deadline or "")
                if next_milestone
                else "",
            },
            "available_actions": {
                "open_tasks": bool(project.task_count),
            },
        }
        if detailed:
            tasks = self._search_scoped(
                "project.task",
                [("project_id", "=", project.id)],
                order="priority desc, date_deadline asc, id desc",
                limit=8,
            )
            plans = self._search_scoped(
                "ftiq.weekly.plan",
                [("project_id", "=", project.id)],
                order="week_start desc, id desc",
                limit=5,
            )
            data["members"] = [
                self._serialize_user(user)
                for user in project.favorite_user_ids.filtered(lambda member: not member.share)
            ]
            data["tasks"] = [
                self._serialize_project_task(task)
                for task in tasks
            ]
            data["plans"] = [
                self._serialize_plan(plan)
                for plan in plans
            ]
            data["activities"] = self._serialize_activities_for_record(project)
        return data

    def _serialize_project_task(self, task, detailed=False):
        linked_daily_task_id = self._safe_related_scoped_id(
            task,
            "ftiq_daily_task_id",
            "ftiq.daily.task",
        )
        linked_plan_id = self._safe_related_scoped_id(
            task,
            "ftiq_plan_id",
            "ftiq.weekly.plan",
        )
        parent_task = self._safe_related_record(task, "parent_id", "project.task")
        data = {
            "id": task.id,
            "name": task.display_name,
            "project": {
                "id": task.project_id.id if task.project_id else False,
                "name": task.project_id.display_name if task.project_id else "",
            },
            "partner": self._serialize_partner_card(task.partner_id) if task.partner_id else {},
            "company": {
                "id": task.company_id.id if task.company_id else False,
                "name": task.company_id.display_name if task.company_id else "",
            },
            "stage": {
                "id": task.stage_id.id if task.stage_id else False,
                "name": task.stage_id.display_name if task.stage_id else "",
            },
            "priority": task.priority or "",
            "date_deadline": str(task.date_deadline or ""),
            "planned_date_begin": fields.Datetime.to_string(task.planned_date_begin)
            if getattr(task, "planned_date_begin", False)
            else None,
            "description": html2plaintext(task.description or "").strip(),
            "parent_task": {
                "id": parent_task.id if parent_task else False,
                "name": parent_task.display_name if parent_task else "",
            },
            "counts": {
                "subtasks": getattr(task, "subtask_count", 0) or 0,
                "closed_subtasks": getattr(task, "closed_subtask_count", 0) or 0,
                "dependencies": getattr(task, "depend_on_count", 0) or 0,
                "dependents": getattr(task, "dependent_tasks_count", 0) or 0,
            },
            "milestone": {
                "id": task.milestone_id.id if getattr(task, "milestone_id", False) else False,
                "name": task.milestone_id.display_name if getattr(task, "milestone_id", False) else "",
            },
            "recurrence": {
                "is_recurring": bool(
                    getattr(task, "recurring_task", False) or getattr(task, "recurrence_id", False)
                ),
                "count": getattr(task, "recurring_count", 0) or 0,
                "interval": getattr(task, "repeat_interval", 0) or 0,
                "unit": getattr(task, "repeat_unit", "") or "",
                "type": getattr(task, "repeat_type", "") or "",
                "until": str(getattr(task, "repeat_until", "") or ""),
            },
            "assigned_users": [
                {
                    "id": user.id,
                    "name": user.display_name,
                }
                for user in task.user_ids
            ],
            "linked_records": {
                "daily_task_id": linked_daily_task_id,
                "plan_id": linked_plan_id,
            },
            "available_actions": {
                "open_daily_task": bool(linked_daily_task_id),
            },
        }
        if detailed:
            data["subtasks"] = [
                {
                    "id": subtask.id,
                    "name": subtask.display_name,
                    "state": subtask.state,
                }
                for subtask in task.child_ids[:8]
            ]
            data["dependencies"] = {
                "blocked_by": [
                    {
                        "id": blocked.id,
                        "name": blocked.display_name,
                        "state": blocked.state,
                    }
                    for blocked in task.depend_on_ids[:8]
                ],
                "dependents": [
                    {
                        "id": dependent.id,
                        "name": dependent.display_name,
                        "state": dependent.state,
                    }
                    for dependent in task.dependent_ids[:8]
                ],
            }
            data["activities"] = self._serialize_activities_for_record(task)
        return data

    def _serialize_team_message(self, message, detailed=False):
        task = self._safe_related_record(message, "task_id", "ftiq.daily.task")
        notification = self._search_scoped(
            "ftiq.mobile.notification",
            [
                ("target_model", "=", "ftiq.team.message"),
                ("target_res_id", "=", message.id),
            ],
            order="is_read asc, create_date desc, id desc",
            limit=1,
        )
        thread_message_count = request.env["mail.message"].search_count(
            [
                ("model", "=", "ftiq.team.message"),
                ("res_id", "=", message.id),
                ("message_type", "!=", "user_notification"),
            ]
        )
        data = {
            "id": message.id,
            "subject": message.subject or "",
            "body": message.body or "",
            "message_type": message.message_type or "note",
            "priority": message.priority or "normal",
            "create_date": fields.Datetime.to_string(message.create_date) if message.create_date else None,
            "write_date": fields.Datetime.to_string(message.write_date) if message.write_date else None,
            "author": self._serialize_user(message.author_id) if message.author_id else {},
            "team": {
                "id": message.team_id.id if message.team_id else False,
                "name": message.team_id.display_name if message.team_id else "",
            },
            "target_user": self._serialize_user(message.target_user_id) if message.target_user_id else {},
            "task": {
                "id": task.id if task else False,
                "name": task.display_name if task else "",
                "state": task.state if task else "",
            },
            "deep_link": self._message_deep_link(message, task_record=task),
            "is_team_wide": bool(message.is_team_wide),
            "notification_id": notification.id if notification else False,
            "is_read": bool(notification.is_read) if notification else True,
            "thread_message_count": thread_message_count,
        }
        if detailed:
            data["activities"] = self._serialize_activities_for_record(message)
        return data

    def _serialize_mobile_notification(self, notification):
        payload = {}
        try:
            payload = json.loads(notification.payload_json or "{}")
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}
        task = request.env["ftiq.daily.task"]
        if notification.target_model == "ftiq.daily.task" and notification.target_res_id:
            task = self._browse_scoped("ftiq.daily.task", notification.target_res_id).exists()
        message_type = payload.get("message_type") or ("alert" if notification.priority == "urgent" else "note")
        return {
            "id": notification.id,
            "subject": notification.name or "",
            "title": notification.name or "",
            "body": notification.body or "",
            "message_type": message_type,
            "category": notification.category or "system",
            "priority": notification.priority or "normal",
            "create_date": fields.Datetime.to_string(notification.create_date) if notification.create_date else None,
            "read_date": fields.Datetime.to_string(notification.read_date) if notification.read_date else None,
            "is_read": bool(notification.is_read),
            "author": self._serialize_user(notification.author_id) if notification.author_id else {},
            "target": {
                "model": notification.target_model or "",
                "id": notification.target_res_id or False,
                "name": notification.target_name or "",
            },
            "task": {
                "id": task.id if task else False,
                "name": task.display_name if task else "",
                "state": task.state if task else "",
            },
            "source_model": notification.source_model or "",
            "source_res_id": notification.source_res_id or False,
            "deep_link": notification.deep_link or "",
            "payload": payload,
        }

    def _serialize_activity(self, activity):
        target = activity._mobile_target_record()
        scoped_target = self._safe_scoped_record(activity.res_model, target)
        target_id = scoped_target.id if scoped_target else False
        target_name = scoped_target.display_name if scoped_target else activity.res_name or ""
        deep_link = request.env["ftiq.mobile.notification"].build_target_deep_link(
            target_model=activity.res_model,
            target_res_id=target_id,
        )
        return {
            "id": activity.id,
            "summary": activity.summary or activity.activity_type_id.display_name or "",
            "note": html2plaintext(activity.note or "").strip(),
            "state": activity.state or "",
            "date_deadline": str(activity.date_deadline or ""),
            "activity_type": {
                "id": activity.activity_type_id.id if activity.activity_type_id else False,
                "name": activity.activity_type_id.display_name if activity.activity_type_id else "",
                "icon": activity.icon or "",
                "category": activity.activity_category or "",
            },
            "assigned_user": self._serialize_user(activity.user_id) if activity.user_id else {},
            "target": {
                "model": activity.res_model or "",
                "id": target_id,
                "name": target_name,
            },
            "deep_link": deep_link,
            "available_actions": {
                "mark_done": bool(
                    activity.can_write
                    and self._mobile_permission("action", "activity.mark_done")
                ),
            },
        }

    def _serialize_activities_for_record(self, record):
        if not record or not getattr(record, "activity_ids", False):
            return []
        activities = request.env["mail.activity"].search(
            [
                ("res_model", "=", record._name),
                ("res_id", "=", record.id),
                ("user_id", "=", self._current_user().id),
                ("active", "=", True),
            ],
            order="date_deadline asc, id asc",
        )
        return [self._serialize_activity(activity) for activity in activities]

    def _serialize_order(self, order, detailed=False):
        is_owner = self._is_current_user_owner(order)
        can_edit = bool(
            is_owner
            and order.state in {"draft", "sent"}
            and self._mobile_permission("action", "order.edit")
        )
        can_confirm = bool(
            is_owner
            and order.state in {"draft", "sent"}
            and self._mobile_permission("action", "order.confirm")
        )
        data = {
            "id": order.id,
            "name": order.name,
            "state": order.state,
            "date_order": fields.Datetime.to_string(order.date_order) if order.date_order else None,
            "partner": self._serialize_partner_card(order.partner_id),
            "user": {
                "id": order.user_id.id if order.user_id else False,
                "name": order.user_id.display_name if order.user_id else "",
            },
            "amount_total": order.amount_total,
            "amount_untaxed": order.amount_untaxed,
            "currency": {
                "id": order.currency_id.id,
                "name": order.currency_id.name,
                "symbol": order.currency_id.symbol,
            },
            "priority": order.ftiq_priority,
            "delivery_notes": order.ftiq_delivery_notes or "",
            "linked_records": {
                "visit_id": order.ftiq_visit_id.id if order.ftiq_visit_id else False,
                "attendance_id": order.ftiq_attendance_id.id if order.ftiq_attendance_id else False,
                "task_id": self._safe_related_scoped_id(
                    order,
                    "ftiq_daily_task_id",
                    "ftiq.daily.task",
                ),
            },
            "available_actions": {
                "edit": can_edit,
                "confirm": can_confirm,
            },
            "ui_actions": self._build_ui_actions(
                ("order.confirm", can_confirm, "primary"),
                ("order.edit", can_edit, "secondary"),
            ),
        }
        if detailed:
            data["lines"] = [{
                "id": line.id,
                "product_id": line.product_id.id,
                "product_name": line.product_id.display_name,
                "quantity": line.product_uom_qty,
                "uom": line.product_uom.display_name if line.product_uom else "",
                "price_unit": line.price_unit,
                "discount": line.discount,
                "subtotal": line.price_subtotal,
                "total": line.price_total,
            } for line in order.order_line.filtered(lambda line: not line.display_type)]
            data["activities"] = self._serialize_activities_for_record(order)
        return data

    def _serialize_purchase_order(self, order, detailed=False):
        can_manage = self._current_role() == "manager"
        can_approve = bool(
            can_manage
            and order.state == "to approve"
            and self._mobile_permission("action", "purchase.approve")
        )
        can_confirm = bool(
            can_manage
            and order.state in {"draft", "sent"}
            and self._mobile_permission("action", "purchase.confirm")
        )
        can_reject = bool(
            can_manage
            and order.state in {"draft", "sent", "to approve", "purchase"}
            and self._mobile_permission("action", "purchase.reject")
        )
        data = {
            "id": order.id,
            "name": order.name or order.display_name,
            "state": order.state,
            "date_order": fields.Datetime.to_string(order.date_order) if order.date_order else None,
            "partner": self._serialize_partner_card(order.partner_id) if order.partner_id else {},
            "user": {
                "id": order.user_id.id if order.user_id else False,
                "name": order.user_id.display_name if order.user_id else "",
            },
            "company": {
                "id": order.company_id.id if order.company_id else False,
                "name": order.company_id.display_name if order.company_id else "",
            },
            "currency": {
                "id": order.currency_id.id if order.currency_id else False,
                "name": order.currency_id.name if order.currency_id else "",
                "symbol": order.currency_id.symbol if order.currency_id else "",
            },
            "amount_total": order.amount_total,
            "amount_untaxed": order.amount_untaxed,
            "amount_tax": order.amount_tax,
            "partner_ref": order.partner_ref or "",
            "origin": order.origin or "",
            "notes": getattr(order, "notes", False) or getattr(order, "note", False) or "",
            "invoice_status": getattr(order, "invoice_status", "") or "",
            "date_planned": fields.Datetime.to_string(order.date_planned)
            if getattr(order, "date_planned", False)
            else None,
            "available_actions": {
                "confirm": can_confirm,
                "approve": can_approve,
                "reject": can_reject,
            },
            "ui_actions": self._build_ui_actions(
                ("purchase.confirm", can_confirm, "primary"),
                ("purchase.approve", can_approve, "primary"),
                ("purchase.reject", can_reject, "destructive"),
            ),
        }
        if detailed:
            lines = order.order_line.filtered(lambda line: not line.display_type)
            data["lines"] = [
                {
                    "id": line.id,
                    "product_id": line.product_id.id if line.product_id else False,
                    "product_name": line.product_id.display_name if line.product_id else line.name or "",
                    "description": line.name or "",
                    "quantity": line.product_qty,
                    "received_qty": line.qty_received,
                    "invoiced_qty": line.qty_invoiced,
                    "uom": line.product_uom.display_name if line.product_uom else "",
                    "price_unit": line.price_unit,
                    "subtotal": line.price_subtotal,
                    "date_planned": fields.Datetime.to_string(line.date_planned)
                    if getattr(line, "date_planned", False)
                    else None,
                }
                for line in lines
            ]
            data["activities"] = self._serialize_activities_for_record(order)
        return data

    def _serialize_invoice(self, invoice, detailed=False):
        due_date = invoice.invoice_date_due
        today = fields.Date.context_today(invoice)
        is_overdue = bool(due_date and invoice.amount_residual > 0 and due_date < today)
        journal = self._safe_related_record(invoice, "journal_id", "account.journal")
        data = {
            "id": invoice.id,
            "name": invoice.name or invoice.display_name,
            "move_name": invoice.display_name,
            "partner_id": invoice.partner_id.id if invoice.partner_id else False,
            "partner_name": invoice.partner_id.display_name if invoice.partner_id else "",
            "invoice_date": str(invoice.invoice_date or ""),
            "due_date": str(invoice.invoice_date_due or ""),
            "state": invoice.state,
            "payment_state": invoice.payment_state,
            "amount_total": invoice.amount_total,
            "amount_residual": invoice.amount_residual,
            "currency": {
                "id": invoice.currency_id.id,
                "name": invoice.currency_id.name,
                "symbol": invoice.currency_id.symbol,
            },
            "is_overdue": is_overdue,
            "available_actions": {
                "create_collection": bool(invoice.partner_id and invoice.amount_residual > 0),
            },
        }
        if detailed:
            collection_lines = self._search_scoped(
                "ftiq.collection.line",
                [("invoice_id", "=", invoice.id)],
                order="id desc",
            )
            lines = invoice.invoice_line_ids.filtered(lambda line: not line.display_type)
            data.update(
                {
                    "partner": self._serialize_partner_card(invoice.partner_id) if invoice.partner_id else {},
                    "journal": {
                        "id": journal.id if journal else False,
                        "name": journal.display_name if journal else "",
                    },
                    "user": {
                        "id": invoice.ftiq_access_user_id.id if invoice.ftiq_access_user_id else False,
                        "name": invoice.ftiq_access_user_id.display_name if invoice.ftiq_access_user_id else "",
                    },
                    "company": {
                        "id": invoice.company_id.id if invoice.company_id else False,
                        "name": invoice.company_id.display_name if invoice.company_id else "",
                    },
                    "invoice_origin": invoice.invoice_origin or "",
                    "reference": invoice.ref or "",
                    "payment_reference": invoice.payment_reference or "",
                    "field_notes": invoice.ftiq_field_notes or "",
                    "line_count": len(lines),
                    "linked_records": {
                        "visit_id": invoice.ftiq_visit_id.id if invoice.ftiq_visit_id else False,
                        "attendance_id": invoice.ftiq_attendance_id.id if invoice.ftiq_attendance_id else False,
                        "task_id": self._safe_related_scoped_id(
                            invoice,
                            "ftiq_daily_task_id",
                            "ftiq.daily.task",
                        ),
                    },
                    "lines": [
                        {
                            "id": line.id,
                            "product_id": line.product_id.id if line.product_id else False,
                            "product_name": line.product_id.display_name if line.product_id else line.name or "",
                            "description": line.name or "",
                            "quantity": line.quantity,
                            "uom": line.product_uom_id.display_name if line.product_uom_id else "",
                            "price_unit": line.price_unit,
                            "discount": line.discount,
                            "subtotal": line.price_subtotal,
                            "total": line.price_total,
                        }
                        for line in lines
                    ],
                    "payment_history": [
                        {
                            "id": line.payment_id.id,
                            "name": line.payment_id.display_name,
                            "date": str(line.payment_id.date or ""),
                            "state": line.payment_id.state,
                            "collection_state": line.payment_id.ftiq_collection_state or "",
                            "amount": line.payment_id.amount,
                            "allocated_amount": line.allocated_amount,
                            "reconciled_amount": line.reconciled_amount,
                            "remaining_amount": line.remaining_amount,
                            "payment_reference": line.payment_id.payment_reference or "",
                            "memo": line.payment_id.memo or "",
                            "currency": {
                                "id": line.payment_id.currency_id.id,
                                "name": line.payment_id.currency_id.name,
                                "symbol": line.payment_id.currency_id.symbol,
                            },
                            "partner": self._serialize_partner_card(line.payment_id.partner_id),
                            "linked_records": {
                                "visit_id": line.payment_id.ftiq_visit_id.id if line.payment_id.ftiq_visit_id else False,
                                "attendance_id": line.payment_id.ftiq_attendance_id.id if line.payment_id.ftiq_attendance_id else False,
                                "task_id": self._safe_related_scoped_id(
                                    line.payment_id,
                                    "ftiq_daily_task_id",
                                    "ftiq.daily.task",
                                ),
                            },
                            "available_actions": {
                                "open_collection": bool(line.payment_id),
                            },
                        }
                        for line in collection_lines
                    ],
                    "activities": self._serialize_activities_for_record(invoice),
                }
            )
        return data

    def _serialize_expense(self, expense, detailed=False):
        is_owner = self._is_current_user_owner(expense)
        can_edit = bool(
            is_owner
            and expense.is_editable
            and expense.state in {"draft", "reported"}
            and self._mobile_permission("action", "expense.edit")
        )
        can_submit = bool(
            is_owner
            and expense.is_editable
            and expense.state in {"draft", "reported"}
            and self._mobile_permission("action", "expense.submit")
        )
        data = {
            "id": expense.id,
            "name": expense.name or expense.product_id.display_name or "",
            "state": expense.state,
            "date": str(expense.date or ""),
            "product": {
                "id": expense.product_id.id if expense.product_id else False,
                "name": expense.product_id.display_name if expense.product_id else "",
            },
            "employee": {
                "id": expense.employee_id.id if expense.employee_id else False,
                "name": expense.employee_id.display_name if expense.employee_id else "",
            },
            "partner": self._serialize_partner_card(expense.ftiq_partner_id) if expense.ftiq_partner_id else {},
            "user": {
                "id": expense.ftiq_user_id.id if expense.ftiq_user_id else False,
                "name": expense.ftiq_user_id.display_name if expense.ftiq_user_id else "",
            },
            "currency": {
                "id": expense.currency_id.id,
                "name": expense.currency_id.name,
                "symbol": expense.currency_id.symbol,
            },
            "quantity": expense.quantity,
            "total_amount_currency": expense.total_amount_currency,
            "total_amount": expense.total_amount,
            "description": expense.description or "",
            "payment_mode": expense.payment_mode,
            "expense_type": expense.ftiq_expense_type or "",
            "receipt_image_name": expense.ftiq_receipt_image_name or "",
            "receipt_image_url": self._image_url("hr.expense", expense.id, "ftiq_receipt_image")
            if expense.ftiq_receipt_image
            else "",
            "linked_records": {
                "visit_id": expense.ftiq_visit_id.id if expense.ftiq_visit_id else False,
                "attendance_id": expense.ftiq_attendance_id.id if expense.ftiq_attendance_id else False,
                "task_id": self._safe_related_scoped_id(
                    expense,
                    "ftiq_daily_task_id",
                    "ftiq.daily.task",
                ),
            },
            "geo": {
                "latitude": expense.ftiq_latitude,
                "longitude": expense.ftiq_longitude,
            },
            "available_actions": {
                "edit": can_edit,
                "submit": can_submit,
            },
            "ui_actions": self._build_ui_actions(
                ("expense.submit", can_submit, "primary"),
                ("expense.edit", can_edit, "secondary"),
            ),
        }
        if detailed:
            data["attachment_count"] = max(expense.nb_attachment, 1 if expense.ftiq_receipt_image else 0)
            data["activities"] = self._serialize_activities_for_record(expense)
        return data

    def _serialize_collection(self, payment, detailed=False):
        is_owner = self._is_current_user_owner(payment)
        can_verify = self._current_role() in {"supervisor", "manager"}
        can_edit = bool(
            is_owner
            and payment.ftiq_collection_state == "draft"
            and payment.state == "draft"
            and self._mobile_permission("action", "collection.edit")
        )
        can_collect = bool(
            is_owner
            and payment.ftiq_collection_state == "draft"
            and self._mobile_permission("action", "collection.collect")
        )
        can_deposit = bool(
            is_owner
            and payment.ftiq_collection_state == "collected"
            and self._mobile_permission("action", "collection.deposit")
        )
        can_verify_action = bool(
            payment.ftiq_collection_state == "deposited"
            and can_verify
            and self._mobile_permission("action", "collection.verify")
        )
        data = {
            "id": payment.id,
            "name": payment.display_name,
            "state": payment.state,
            "collection_state": payment.ftiq_collection_state or "",
            "date": str(payment.date or ""),
            "partner": self._serialize_partner_card(payment.partner_id),
            "amount": payment.amount,
            "currency": {
                "id": payment.currency_id.id,
                "name": payment.currency_id.name,
                "symbol": payment.currency_id.symbol,
            },
            "journal": {
                "id": payment.journal_id.id,
                "name": payment.journal_id.display_name,
            },
            "payment_method": {
                "id": payment.payment_method_line_id.id if payment.payment_method_line_id else False,
                "name": payment.payment_method_line_id.display_name if payment.payment_method_line_id else "",
            },
            "memo": payment.memo or "",
            "payment_reference": payment.payment_reference or "",
            "check_number": payment.ftiq_check_number or "",
            "check_date": str(payment.ftiq_check_date or ""),
            "bank_name": payment.ftiq_bank_name or "",
            "allocated_amount": payment.ftiq_allocated_amount,
            "unallocated_amount": payment.ftiq_unallocated_amount,
            "linked_records": {
                "visit_id": payment.ftiq_visit_id.id if payment.ftiq_visit_id else False,
                "attendance_id": payment.ftiq_attendance_id.id if payment.ftiq_attendance_id else False,
                "task_id": self._safe_related_scoped_id(
                    payment,
                    "ftiq_daily_task_id",
                    "ftiq.daily.task",
                ),
            },
            "receipt_image_url": self._image_url("account.payment", payment.id, "ftiq_receipt_image") if payment.ftiq_receipt_image else "",
            "available_actions": {
                "edit": can_edit,
                "collect": can_collect,
                "deposit": can_deposit,
                "verify": can_verify_action,
            },
            "ui_actions": self._build_ui_actions(
                ("collection.collect", can_collect, "primary"),
                ("collection.deposit", can_deposit, "primary"),
                ("collection.verify", can_verify_action, "primary"),
                ("collection.edit", can_edit, "secondary"),
            ),
        }
        if detailed:
            data["allocations"] = [{
                "id": line.id,
                "invoice_id": line.invoice_id.id,
                "invoice_name": line.invoice_id.display_name,
                "invoice_date": str(line.invoice_date or ""),
                "due_date": str(line.due_date or ""),
                "invoice_residual": line.invoice_residual,
                "invoice_residual_payment": line.invoice_residual_payment,
                "allocated_amount": line.allocated_amount,
                "reconciled_amount": line.reconciled_amount,
                "remaining_amount": line.remaining_amount,
            } for line in payment.ftiq_collection_line_ids]
            data["open_invoices"] = [self._serialize_invoice(invoice) for invoice in payment._get_ftiq_open_invoices()]
            data["activities"] = self._serialize_activities_for_record(payment)
        return data

    def _serialize_stock_check(self, stock_check, detailed=False):
        is_owner = self._is_current_user_owner(stock_check)
        can_review = self._current_role() in {"supervisor", "manager"}
        can_edit = bool(
            is_owner
            and stock_check.state == "draft"
            and self._mobile_permission("action", "stock_check.edit")
        )
        can_submit = bool(
            is_owner
            and stock_check.state == "draft"
            and self._mobile_permission("action", "stock_check.submit")
        )
        can_review_action = bool(
            stock_check.state == "submitted"
            and can_review
            and self._mobile_permission("action", "stock_check.review")
        )
        can_reset = bool(
            stock_check.state == "submitted"
            and can_review
            and self._mobile_permission("action", "stock_check.reset")
        )
        data = {
            "id": stock_check.id,
            "name": stock_check.display_name,
            "state": stock_check.state,
            "check_date": fields.Datetime.to_string(stock_check.check_date) if stock_check.check_date else None,
            "partner": self._serialize_partner_card(stock_check.partner_id),
            "user": {
                "id": stock_check.user_id.id if stock_check.user_id else False,
                "name": stock_check.user_id.display_name if stock_check.user_id else "",
            },
            "line_count": len(stock_check.line_ids),
            "total_qty": stock_check.total_qty,
            "notes": stock_check.notes or "",
            "latitude": stock_check.latitude,
            "longitude": stock_check.longitude,
            "photo_url": self._image_url("ftiq.stock.check", stock_check.id, "photo") if stock_check.photo else "",
            "linked_records": {
                "visit_id": stock_check.visit_id.id if stock_check.visit_id else False,
                "attendance_id": stock_check.attendance_id.id if stock_check.attendance_id else False,
                "task_id": self._safe_related_scoped_id(
                    stock_check,
                    "ftiq_daily_task_id",
                    "ftiq.daily.task",
                ),
            },
            "available_actions": {
                "edit": can_edit,
                "submit": can_submit,
                "review": can_review_action,
                "reset": can_reset,
            },
            "ui_actions": self._build_ui_actions(
                ("stock_check.submit", can_submit, "primary"),
                ("stock_check.review", can_review_action, "primary"),
                ("stock_check.edit", can_edit, "secondary"),
                ("stock_check.reset", can_reset, "destructive"),
            ),
        }
        if detailed:
            data["lines"] = [{
                "id": line.id,
                "product_id": line.product_id.id,
                "product_name": line.product_id.display_name,
                "stock_qty": line.stock_qty,
                "expiry_date": str(line.expiry_date or ""),
                "batch_number": line.batch_number or "",
                "shelf_position": line.shelf_position or "",
                "competitor_product": line.competitor_product or "",
                "competitor_qty": line.competitor_qty,
                "note": line.note or "",
                "sequence": line.sequence,
            } for line in stock_check.line_ids.sorted(key=lambda line: (line.sequence, line.id))]
            data["activities"] = self._serialize_activities_for_record(stock_check)
        return data

    def _serialize_product(self, product):
        template = product.product_tmpl_id
        description = (
            getattr(product, "description_sale", False)
            or getattr(template, "description_sale", False)
            or getattr(product, "description", False)
            or getattr(template, "description", False)
            or ""
        )
        currency = request.env.company.currency_id
        return {
            "id": product.id,
            "name": product.display_name,
            "default_code": product.default_code or "",
            "barcode": product.barcode or "",
            "category_name": product.categ_id.display_name if product.categ_id else "",
            "description": description,
            "list_price": product.lst_price,
            "currency_symbol": currency.symbol if currency else "",
            "uom": product.uom_id.display_name if product.uom_id else "",
            "image_url": self._image_url("product.product", product.id, "image_128") if getattr(product, "image_128", False) else "",
        }

    def _serialize_call_reason(self, call_reason):
        return {
            "id": call_reason.id,
            "name": call_reason.display_name,
        }

    def _serialize_material(self, material):
        return {
            "id": material.id,
            "name": material.display_name,
            "product_id": material.product_id.id if material.product_id else False,
            "product_name": material.product_id.display_name if material.product_id else "",
            "call_reason_id": material.call_reason_id.id if material.call_reason_id else False,
            "call_reason_name": material.call_reason_id.display_name if material.call_reason_id else "",
            "material_scope": material.material_scope,
            "material_type": material.material_type,
            "description": material.description or "",
            "image_url": self._image_url("ftiq.marketing.material", material.id, "image") if material.image else "",
            "file_url": self._image_url("ftiq.marketing.material", material.id, "file") if material.file else "",
        }

    def _serialize_payment_journal(self, journal):
        payment_methods = [{
            "id": line.id,
            "name": line.display_name,
            "code": line.code,
        } for line in journal._get_available_payment_method_lines("inbound")]
        currency = journal.currency_id or journal.company_id.currency_id
        return {
            "id": journal.id,
            "name": journal.display_name,
            "type": journal.type,
            "currency": {
                "id": currency.id,
                "name": currency.name,
                "symbol": currency.symbol,
            },
            "payment_methods": payment_methods,
        }
