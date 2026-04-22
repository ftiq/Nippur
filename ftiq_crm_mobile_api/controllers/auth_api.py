import odoo
import odoo.http as odoo_http
import odoo.modules.registry
from odoo import _, api, fields, http
from odoo.http import request

from .base_api import FtiqCrmApiBase


class FtiqCrmAuthApi(FtiqCrmApiBase):
    @http.route("/api/auth/login/", type="http", auth="none", methods=["POST"], cors="*", csrf=False)
    def login(self, **kwargs):
        return self._dispatch(self._login)

    @http.route("/api/auth/google/", type="http", auth="none", methods=["POST"], cors="*", csrf=False)
    def google_login(self, **kwargs):
        return self._dispatch(self._google_login)

    @http.route("/api/auth/refresh-token/", type="http", auth="none", methods=["POST"], cors="*", csrf=False)
    def refresh_token(self, **kwargs):
        return self._dispatch(self._refresh_token)

    @http.route("/api/auth/me/", type="http", auth="none", methods=["GET"], cors="*", csrf=False)
    def me(self, **kwargs):
        return self._dispatch(self._me)

    @http.route("/api/auth/profile/", type="http", auth="none", methods=["GET"], cors="*", csrf=False)
    def profile(self, **kwargs):
        return self._dispatch(self._profile)

    @http.route("/api/auth/switch-org/", type="http", auth="none", methods=["POST"], cors="*", csrf=False)
    def switch_org(self, **kwargs):
        return self._dispatch(self._switch_org)

    def _login(self):
        payload = self._json_body()
        db = (payload.get("db") or self._request_database()).strip()
        login = (payload.get("login") or payload.get("username") or "").strip()
        password = payload.get("password") or ""
        if not db or not login or not password:
            return self._error(_("Database, username, and password are required."))

        if request.db and request.db != db:
            request.env.cr.close()
        elif request.db:
            request.env.cr.rollback()

        if not odoo_http.db_filter([db]):
            return self._error(_("Database not found."), status=404)

        credential = {"login": login, "password": password, "type": "password"}
        auth_info = request.session.authenticate(db, credential)
        if auth_info["uid"] != request.session.uid:
            return self._error(
                _("Multi-factor authentication is not supported by this mobile client."),
                status=409,
            )

        request.session.db = db
        registry = odoo.modules.registry.Registry(db)
        with registry.cursor() as cr:
            env = api.Environment(cr, request.session.uid, request.session.context)
            odoo_http.root.session_store.rotate(request.session, env)
            request.update_env(user=request.session.uid)
            user = env.user
            if user.share or not user.active:
                request.session.logout(keep_db=True)
                return self._error(_("Only active internal Odoo users can use this app."), status=403)
            token = self._issue_token(user, env=env)
            data = self._auth_payload(user, token)
            data["session"] = {
                "uid": user.id,
                "db": db,
                "server_time": fields.Datetime.to_string(fields.Datetime.now()),
            }
            return self._json(data)

    def _google_login(self):
        return self._error(
            _("Use your Odoo username and password to sign in."),
            status=400,
        )

    def _refresh_token(self):
        payload = self._json_body()
        token = (payload.get("refresh") or payload.get("token") or self._bearer_token() or "").strip()
        if not token:
            return self._error(_("Refresh token is required."), status=401)
        decoded = self._decode_token_payload(token)
        user = request.env["res.users"].sudo().browse(int(decoded.get("uid") or 0)).exists()
        if not user or not user.active or user.share:
            return self._error(_("Invalid mobile user."), status=401)
        return self._json(
            {
                "access": self._issue_token(user),
                "refresh": self._issue_token(user),
            }
        )

    def _me(self):
        user = self._authenticate()
        return self._json(self._serialize_user(user))

    def _profile(self):
        user = self._authenticate()
        default_country = user.company_id.account_fiscal_country_id or user.company_id.country_id
        return self._json(
            {
                "id": str(user.id),
                "user": self._serialize_user(user),
                "org": {
                    "id": str(user.company_id.id),
                    "name": user.company_id.name,
                    "api_key": "",
                    "default_currency": user.company_id.currency_id.name if user.company_id.currency_id else "",
                    "currency_symbol": user.company_id.currency_id.symbol if user.company_id.currency_id else "",
                    "default_country": default_country.name if default_country else "",
                    "default_country_id": str(default_country.id) if default_country else "",
                },
                "role": "ADMIN" if user.has_group("base.group_system") else "USER",
                "is_organization_admin": user.has_group("base.group_system"),
                "has_sales_access": user.has_group("sales_team.group_sale_salesman"),
                "has_marketing_access": user.has_group("sales_team.group_sale_salesman"),
                "phone": user.phone or "",
                "date_of_joining": "",
                "is_active": bool(user.active),
            }
        )

    def _switch_org(self):
        user = self._authenticate()
        token = self._issue_token(user)
        return self._json(
            {
                "access_token": token,
                "refresh_token": token,
                "organization": {
                    "id": str(user.company_id.id),
                    "name": user.company_id.name,
                },
            }
        )

    def _auth_payload(self, user, token):
        default_country = user.company_id.account_fiscal_country_id or user.company_id.country_id
        return {
            "JWTtoken": token,
            "refresh_token": token,
            "user": self._serialize_user(user),
            "organizations": [
                {
                    "id": str(user.company_id.id),
                    "name": user.company_id.name,
                    "role": "ADMIN" if user.has_group("base.group_system") else "USER",
                    "default_currency": user.company_id.currency_id.name if user.company_id.currency_id else "",
                    "currency_symbol": user.company_id.currency_id.symbol if user.company_id.currency_id else "",
                    "default_country": default_country.name if default_country else "",
                    "default_country_id": str(default_country.id) if default_country else "",
                    "is_organization_admin": user.has_group("base.group_system"),
                    "has_sales_access": user.has_group("sales_team.group_sale_salesman"),
                    "has_marketing_access": user.has_group("sales_team.group_sale_salesman"),
                }
            ],
        }
