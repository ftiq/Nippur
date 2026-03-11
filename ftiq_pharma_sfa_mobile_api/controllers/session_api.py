import odoo
import odoo.http as odoo_http
import odoo.modules.registry
from odoo import _, api, fields, http
from odoo.http import request

from .base_api import FtiqMobileApiBase


class FtiqMobileSessionApi(FtiqMobileApiBase):
    def _mobile_access_message(self):
        return _("You do not have permission to use the FTIQ mobile application. Contact your administrator.")

    def _has_mobile_access(self, user):
        return any(
            user.has_group(group_xmlid)
            for group_xmlid in (
                "ftiq_pharma_sfa.group_ftiq_rep",
                "ftiq_pharma_sfa.group_ftiq_supervisor",
                "ftiq_pharma_sfa.group_ftiq_manager",
            )
        )

    def _ensure_mobile_access(self, user):
        if not self._has_mobile_access(user):
            return self._error(
                self._mobile_access_message(),
                status=403,
                code="mobile_access_denied",
            )
        return None

    @http.route("/ftiq_mobile_api/v1/session/login", type="http", auth="none", methods=["POST"], csrf=False)
    def login(self, **kwargs):
        return self._dispatch(self._login)

    @http.route("/ftiq_mobile_api/v1/session/logout", type="http", auth="user", methods=["POST"], csrf=False)
    def logout(self, **kwargs):
        return self._dispatch(self._logout)

    @http.route("/ftiq_mobile_api/v1/session/me", type="http", auth="user", methods=["GET"], csrf=False)
    def me(self, **kwargs):
        return self._dispatch(self._me)

    @http.route("/ftiq_mobile_api/v1/bootstrap", type="http", auth="user", methods=["GET"], csrf=False)
    def bootstrap(self, **kwargs):
        return self._dispatch(self._bootstrap)

    @http.route("/ftiq_mobile_api/v1/mobile/device/register", type="http", auth="user", methods=["POST"], csrf=False)
    def register_device(self, **kwargs):
        return self._dispatch(self._register_device)

    def _login(self):
        payload = self._json_body()
        db = (payload.get("db") or "").strip()
        login = (payload.get("login") or "").strip()
        password = payload.get("password") or ""
        if not db or not login or not password:
            return self._error(_("Database, login, and password are required."))

        if request.db and request.db != db:
            request.env.cr.close()
        elif request.db:
            request.env.cr.rollback()

        if not odoo_http.db_filter([db]):
            return self._error(_("Database not found."), status=404, code="database_not_found")

        credential = {"login": login, "password": password, "type": "password"}
        auth_info = request.session.authenticate(db, credential)
        if auth_info["uid"] != request.session.uid:
            return self._error(
                _("Multi-factor authentication is not supported by this mobile client."),
                status=409,
                code="mfa_required",
            )

        request.session.db = db
        registry = odoo.modules.registry.Registry(db)
        with registry.cursor() as cr:
            env = api.Environment(cr, request.session.uid, request.session.context)
            if not request.db:
                odoo_http.root.session_store.rotate(request.session, env)
                request.future_response.set_cookie(
                    "session_id",
                    request.session.sid,
                    max_age=odoo_http.get_session_max_inactivity(env),
                    httponly=True,
                    secure=request.httprequest.scheme == "https",
                    samesite="Lax",
                )
            user = env.user
            denied = self._ensure_mobile_access(user)
            if denied:
                request.session.logout(keep_db=True)
                return denied
            data = {
                "session": {
                    "uid": user.id,
                    "db": db,
                    "server_time": fields.Datetime.to_string(fields.Datetime.now()),
                },
                "user": self._serialize_user(user),
            }
            return self._ok(data)

    def _logout(self):
        request.session.logout(keep_db=True)
        return self._ok({"logged_out": True})

    def _me(self):
        denied = self._ensure_mobile_access(self._current_user())
        if denied:
            return denied
        return self._ok({
            "user": self._serialize_user(self._current_user()),
        })

    def _bootstrap(self):
        user = self._current_user()
        denied = self._ensure_mobile_access(user)
        if denied:
            return denied
        platform = request.httprequest.args.get("platform", "")
        app_version = request.httprequest.args.get("app_version", "")
        build_number = request.httprequest.args.get("build_number", "")
        installation_id = request.httprequest.args.get("installation_id", "")
        device = self._current_mobile_device(installation_id).exists()
        attendance = request.env["ftiq.field.attendance"].get_active_attendance(
            user.id,
            fields.Date.context_today(user),
        )
        today_tasks = request.env["ftiq.daily.task"].search(
            [("user_id", "=", user.id)],
            order="scheduled_date asc, priority desc",
            limit=5,
        )
        return self._ok({
            "user": self._serialize_user(user),
            "company": self._serialize_company(user.company_id),
            "active_attendance": self._serialize_attendance(attendance),
            "today_tasks": [self._serialize_task(task) for task in today_tasks],
            "mobile_runtime": self._serialize_mobile_runtime(
                platform=platform,
                app_version=app_version,
                build_number=build_number,
                device=device,
            ),
        })

    def _register_device(self):
        denied = self._ensure_mobile_access(self._current_user())
        if denied:
            return denied
        payload = self._json_body()
        metadata = self._client_request_metadata()
        device = request.env["ftiq.mobile.device"].register_current(
            payload,
            remote_ip=metadata["ip"],
            user_agent=metadata["user_agent"],
        )
        return self._ok({
            "user": self._serialize_user(self._current_user()),
            "device": self._serialize_mobile_device(device),
            "mobile_runtime": self._serialize_mobile_runtime(
                platform=payload.get("platform") or "",
                app_version=payload.get("app_version") or "",
                build_number=payload.get("build_number") or "",
                device=device,
            ),
        })
