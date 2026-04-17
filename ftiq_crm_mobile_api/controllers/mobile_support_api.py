from odoo import _, http
from odoo.http import request
from odoo.osv import expression

from .base_api import FtiqCrmApiBase


class FtiqCrmMobileSupportApi(FtiqCrmApiBase):
    @http.route("/api/clients/", type="http", auth="none", methods=["GET"], csrf=False)
    def clients(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._clients))

    @http.route("/api/clients/<int:partner_id>/", type="http", auth="none", methods=["GET"], csrf=False)
    def client_detail(self, partner_id, **kwargs):
        return self._dispatch(lambda: self._with_auth(lambda: self._client_detail(partner_id)))

    @http.route("/api/clients/<int:partner_id>/open-invoices/", type="http", auth="none", methods=["GET"], csrf=False)
    def client_open_invoices(self, partner_id, **kwargs):
        return self._dispatch(lambda: self._with_auth(lambda: self._client_open_invoices(partner_id)))

    @http.route("/api/clients/<int:partner_id>/location/", type="http", auth="none", methods=["POST"], csrf=False)
    def client_update_location(self, partner_id, **kwargs):
        return self._dispatch(lambda: self._with_auth(lambda: self._client_update_location(partner_id)))

    @http.route("/api/mobile/device/register/", type="http", auth="none", methods=["POST"], csrf=False)
    def register_device(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._register_device))

    @http.route("/api/notifications/", type="http", auth="none", methods=["GET"], csrf=False)
    def notifications(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._notifications))

    @http.route("/api/notifications/read/", type="http", auth="none", methods=["POST"], csrf=False)
    def notifications_read(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._notifications_read))

    def _with_auth(self, callback):
        self._authenticate()
        return callback()

    def _client_domain(self):
        domain = [("type", "!=", "private")]
        search = (self._arg("search") or "").strip()
        if search:
            domain = expression.AND(
                [
                    domain,
                    self._domain_for_search(
                        ["name", "email", "phone", "mobile", "city", "street", "zip", "comment"],
                        search,
                    ),
                ]
            )
        return domain

    def _browse_client(self, partner_id):
        return (
            request.env["res.partner"]
            .with_context(active_test=False)
            .browse(partner_id)
            .exists()
        )

    def _client_invoices(self, partner):
        commercial_partner = partner.commercial_partner_id or partner
        if not commercial_partner or not self._has_model("account.move"):
            return request.env["account.move"]
        return request.env["account.move"].search(
            self._open_invoice_domain(commercial_partner.ids),
            order="invoice_date_due asc, invoice_date asc, id desc",
        )

    def _serialize_client(self, partner, metrics=None, include_invoices=False):
        commercial = partner.commercial_partner_id or partner
        location = self._partner_mobile_location(commercial)
        metrics = metrics or {"due_amount": 0.0, "open_invoice_count": 0}
        invoices = self._client_invoices(partner) if include_invoices else request.env["account.move"]
        return {
            "id": str(partner.id),
            "commercial_partner_id": str(commercial.id),
            "name": partner.display_name,
            "display_name": partner.display_name,
            "email": partner.email or "",
            "phone": partner.phone or "",
            "mobile": partner.mobile or "",
            "street": partner.street or "",
            "city": partner.city or "",
            "state": partner.state_id.name if partner.state_id else "",
            "country": partner.country_id.name if partner.country_id else "",
            "postcode": partner.zip or "",
            "address": partner.contact_address_complete or partner.contact_address or "",
            "parent_name": partner.parent_id.display_name if partner.parent_id else "",
            "job_title": partner.function or "",
            "notes": partner.comment or "",
            "is_company": bool(partner.is_company),
            "due_amount": metrics.get("due_amount", 0.0),
            "open_invoice_count": metrics.get("open_invoice_count", 0),
            "currency": (
                commercial.company_id.currency_id.name
                if commercial.company_id and commercial.company_id.currency_id
                else request.env.company.currency_id.name
            ),
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "location_accuracy": location["accuracy"],
            "location_is_mock": location["is_mock"],
            "location_at": location["location_at"],
            "tags": [tag.display_name for tag in partner.category_id],
            "open_invoices": [self._serialize_invoice_summary(move) for move in invoices[:10]],
        }

    def _clients(self):
        limit, offset = self._limit_offset()
        Partner = request.env["res.partner"].with_context(active_test=False)
        domain = self._client_domain()
        count = Partner.search_count(domain)
        partners = Partner.search(domain, order="name, id", limit=limit, offset=offset)
        metrics = self._invoice_metrics_by_partner(partners)
        items = []
        for partner in partners:
            commercial = partner.commercial_partner_id or partner
            items.append(
                self._serialize_client(
                    partner,
                    metrics=metrics.get(
                        commercial.id,
                        {"due_amount": 0.0, "open_invoice_count": 0},
                    ),
                )
            )
        next_offset = offset + len(items)
        return self._json(
            {
                "items": items,
                "count": count,
                "limit": limit,
                "offset": offset,
                "next_offset": next_offset if next_offset < count else None,
            }
        )

    def _client_detail(self, partner_id):
        partner = self._browse_client(partner_id)
        if not partner:
            return self._error(_("Client not found."), status=404)
        commercial = partner.commercial_partner_id or partner
        metrics = self._invoice_metrics_by_partner(partner)
        data = self._serialize_client(
            partner,
            metrics=metrics.get(commercial.id, {"due_amount": 0.0, "open_invoice_count": 0}),
            include_invoices=True,
        )
        return self._json(data)

    def _client_open_invoices(self, partner_id):
        partner = self._browse_client(partner_id)
        if not partner:
            return self._error(_("Client not found."), status=404)
        invoices = self._client_invoices(partner)
        return self._json(
            {
                "items": [self._serialize_invoice_summary(move) for move in invoices],
                "count": len(invoices),
            }
        )

    def _client_update_location(self, partner_id):
        partner = self._browse_client(partner_id)
        if not partner:
            return self._error(_("Client not found."), status=404)
        payload = self._json_body()
        location = self._location_payload(payload)
        if not location:
            return self._error(_("Latitude and longitude are required."))
        self._apply_mobile_location(partner, payload, partner=partner.commercial_partner_id or partner)
        return self._ok_message(_("Client location updated successfully."))

    def _register_device(self):
        payload = self._json_body()
        installation_id = (payload.get("installation_id") or "").strip()
        if not installation_id:
            return self._error(_("installation_id is required."))
        Device = request.env["ftiq.mobile.device"].sudo()
        device = Device.search([("installation_id", "=", installation_id)], limit=1)
        values = {
            "name": (payload.get("device_name") or _("Mobile Device")).strip() or _("Mobile Device"),
            "installation_id": installation_id,
            "user_id": request.env.user.id,
            "platform": (payload.get("platform") or "").strip(),
            "device_name": (payload.get("device_name") or "").strip(),
            "device_model": (payload.get("device_model") or "").strip(),
            "app_version": (payload.get("app_version") or "").strip(),
            "build_number": (payload.get("build_number") or "").strip(),
            "locale": (payload.get("locale") or "").strip(),
            "notification_enabled": self._payload_bool(payload, "notification_enabled", False),
            "location_enabled": self._payload_bool(payload, "location_enabled", False),
            "fcm_token": (payload.get("fcm_token") or "").strip(),
            "last_seen_at": request.env.cr.now(),
            "last_registration_at": request.env.cr.now(),
            "active": True,
        }
        if device:
            device.write(values)
        else:
            device = Device.create(values)
        return self._json(
            {
                "error": False,
                "device": {
                    "id": device.id,
                    "installation_id": device.installation_id,
                    "platform": device.platform or "",
                    "fcm_token": bool(device.fcm_token),
                    "notification_enabled": bool(device.notification_enabled),
                },
            }
        )

    def _notification_domain(self):
        domain = [
            ("res_partner_id", "=", request.env.user.partner_id.id),
            ("mail_message_id", "!=", False),
        ]
        if self._arg("unread_only") in {"1", "true", "True"}:
            domain.append(("is_read", "=", False))
        return domain

    def _notifications(self):
        limit = self._arg_int("limit", 40)
        notifications = request.env["mail.notification"].sudo().search(
            self._notification_domain(),
            order="id desc",
            limit=limit,
        )
        unread_count = request.env["mail.notification"].sudo().search_count(
            [
                ("res_partner_id", "=", request.env.user.partner_id.id),
                ("mail_message_id", "!=", False),
                ("is_read", "=", False),
            ]
        )
        return self._json(
            {
                "items": [self._serialize_mail_notification(notification) for notification in notifications],
                "count": len(notifications),
                "unread_count": unread_count,
            }
        )

    def _notifications_read(self):
        payload = self._json_body()
        mark_all = self._payload_bool(payload, "mark_all", False)
        ids = []
        for item in payload.get("ids") or []:
            try:
                ids.append(int(item))
            except Exception:
                continue
        domain = [
            ("res_partner_id", "=", request.env.user.partner_id.id),
            ("mail_message_id", "!=", False),
        ]
        if mark_all:
            domain.append(("is_read", "=", False))
        else:
            domain.append(("id", "in", ids or [0]))
        notifications = request.env["mail.notification"].sudo().search(domain)
        if notifications:
            notifications.write({"is_read": True})
        return self._json(
            {
                "error": False,
                "updated": len(notifications),
            }
        )
