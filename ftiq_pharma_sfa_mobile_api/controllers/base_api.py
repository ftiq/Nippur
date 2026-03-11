import json
import logging

from odoo import _, fields, http
from odoo.exceptions import AccessDenied, AccessError, UserError, ValidationError
from odoo.http import request
from odoo.osv import expression


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

    def _geo_context_from_payload(self, payload):
        return {
            "ftiq_latitude": payload.get("latitude"),
            "ftiq_longitude": payload.get("longitude"),
            "ftiq_accuracy": payload.get("accuracy", 0),
            "ftiq_is_mock": self._payload_bool(payload, "is_mock", False),
        }

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
        if model_name == "ftiq.mobile.runtime.policy":
            return [("company_id", "=", user.company_id.id)]
        return []

    def _search_scoped(self, model_name, domain=None, order=None, limit=None):
        model = request.env[model_name]
        final_domain = expression.AND([self._scope_domain(model_name), domain or []])
        return model.search(final_domain, order=order, limit=limit)

    def _browse_scoped(self, model_name, record_id):
        return self._search_scoped(model_name, [("id", "=", record_id)], limit=1)[:1]

    def _safe_scoped_record(self, model_name, record):
        if not record:
            return request.env[model_name]
        try:
            record_id = record.id
        except AccessError:
            return request.env[model_name]
        if not record_id:
            return request.env[model_name]
        try:
            return self._browse_scoped(model_name, record_id).exists()
        except AccessError:
            return request.env[model_name]

    def _safe_scoped_id(self, model_name, record):
        scoped_record = self._safe_scoped_record(model_name, record)
        return scoped_record.id if scoped_record else False

    def _owner_field_for(self, record_or_model):
        model_name = record_or_model if isinstance(record_or_model, str) else getattr(record_or_model, "_name", "")
        return self._OWNER_FIELD_BY_MODEL.get(model_name)

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
        return {
            "id": user.id,
            "name": user.display_name,
            "login": user.login,
            "role": self._role_of(user),
            "email": user.email or user.partner_id.email or "",
            "phone": user.partner_id.phone or "",
            "mobile": user.partner_id.mobile or "",
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
                "check_out": attendance.state == "checked_in",
            },
        }

    def _serialize_partner_card(self, partner):
        return {
            "id": partner.id,
            "name": partner.display_name,
            "client_code": partner.ftiq_client_code or "",
            "client_type": partner.ftiq_client_type or "client",
            "client_type_label": partner.ftiq_client_type_label or "",
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
            "available_actions": {
                "edit": is_owner and visit.state in ("draft", "in_progress", "returned"),
                "start": is_owner and visit.state == "draft",
                "end": is_owner and visit.state == "in_progress",
                "submit": is_owner and visit.state in ("in_progress", "returned"),
                "approve": visit.state == "submitted" and can_review,
                "return": visit.state == "submitted" and can_review,
                "create_order": is_owner and visit.state == "in_progress",
                "create_collection": is_owner and visit.state == "in_progress",
                "create_stock_check": is_owner and visit.state == "in_progress",
            },
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
                "task_id": self._safe_scoped_id("ftiq.daily.task", line.daily_task_id),
            } for line in plan.line_ids.sorted(key=lambda item: ((item.scheduled_date or fields.Date.today()), item.sequence, item.id))]
        return data

    def _serialize_task(self, task):
        is_owner = self._is_current_user_owner(task)
        role = self._current_role()
        return {
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
            },
            "available_actions": {
                "edit": is_owner and task.state in ("draft", "pending", "in_progress", "returned"),
                "start": is_owner and task.state in ("draft", "pending", "returned"),
                "complete": is_owner and task.state == "in_progress",
                "submit": is_owner and task.state in ("in_progress", "completed", "returned") and task.confirmation_required,
                "confirm": task.state == "submitted" and role in {"supervisor", "manager"},
                "return": task.state == "submitted" and role in {"supervisor", "manager"},
            },
        }

    def _serialize_team_message(self, message):
        task = self._safe_scoped_record("ftiq.daily.task", message.task_id)
        return {
            "id": message.id,
            "subject": message.subject or "",
            "body": message.body or "",
            "message_type": message.message_type or "note",
            "priority": message.priority or "normal",
            "create_date": fields.Datetime.to_string(message.create_date) if message.create_date else None,
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
            "is_team_wide": bool(message.is_team_wide),
        }

    def _serialize_order(self, order, detailed=False):
        is_owner = self._is_current_user_owner(order)
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
                "task_id": self._safe_scoped_id("ftiq.daily.task", order.ftiq_daily_task_id),
            },
            "available_actions": {
                "edit": is_owner and order.state in {"draft", "sent"},
                "confirm": is_owner and order.state in {"draft", "sent"},
            },
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
        return data

    def _serialize_invoice(self, invoice, detailed=False):
        due_date = invoice.invoice_date_due
        today = fields.Date.context_today(invoice)
        is_overdue = bool(due_date and invoice.amount_residual > 0 and due_date < today)
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
                        "id": invoice.journal_id.id if invoice.journal_id else False,
                        "name": invoice.journal_id.display_name if invoice.journal_id else "",
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
                        "task_id": self._safe_scoped_id("ftiq.daily.task", invoice.ftiq_daily_task_id),
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
                                "task_id": self._safe_scoped_id("ftiq.daily.task", line.payment_id.ftiq_daily_task_id),
                            },
                            "available_actions": {
                                "open_collection": bool(line.payment_id),
                            },
                        }
                        for line in collection_lines
                    ],
                }
            )
        return data

    def _serialize_expense(self, expense, detailed=False):
        is_owner = self._is_current_user_owner(expense)
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
                "task_id": self._safe_scoped_id("ftiq.daily.task", expense.ftiq_daily_task_id),
            },
            "geo": {
                "latitude": expense.ftiq_latitude,
                "longitude": expense.ftiq_longitude,
            },
            "available_actions": {
                "edit": bool(is_owner and expense.is_editable and expense.state in {"draft", "reported"}),
                "submit": bool(is_owner and expense.is_editable and expense.state in {"draft", "reported"}),
            },
        }
        if detailed:
            data["attachment_count"] = max(expense.nb_attachment, 1 if expense.ftiq_receipt_image else 0)
        return data

    def _serialize_collection(self, payment, detailed=False):
        is_owner = self._is_current_user_owner(payment)
        can_verify = self._current_role() in {"supervisor", "manager"}
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
                "task_id": self._safe_scoped_id("ftiq.daily.task", payment.ftiq_daily_task_id),
            },
            "receipt_image_url": self._image_url("account.payment", payment.id, "ftiq_receipt_image") if payment.ftiq_receipt_image else "",
            "available_actions": {
                "edit": is_owner and payment.ftiq_collection_state == "draft" and payment.state == "draft",
                "collect": is_owner and payment.ftiq_collection_state == "draft",
                "deposit": is_owner and payment.ftiq_collection_state == "collected",
                "verify": payment.ftiq_collection_state == "deposited" and can_verify,
            },
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
        return data

    def _serialize_stock_check(self, stock_check, detailed=False):
        is_owner = self._is_current_user_owner(stock_check)
        can_review = self._current_role() in {"supervisor", "manager"}
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
                "task_id": self._safe_scoped_id("ftiq.daily.task", stock_check.ftiq_daily_task_id),
            },
            "available_actions": {
                "edit": is_owner and stock_check.state == "draft",
                "submit": is_owner and stock_check.state == "draft",
                "review": stock_check.state == "submitted" and can_review,
                "reset": stock_check.state == "submitted" and can_review,
            },
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
