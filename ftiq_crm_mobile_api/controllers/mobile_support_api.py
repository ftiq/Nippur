import base64

from odoo import _, fields, http
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.osv import expression

from .base_api import FtiqCrmApiBase


class FtiqCrmMobileSupportApi(FtiqCrmApiBase):
    @http.route("/api/clients/", type="http", auth="none", methods=["GET", "POST"], cors="*", csrf=False)
    def clients(self, **kwargs):
        if request.httprequest.method == "POST":
            return self._dispatch(lambda: self._with_auth(self._client_create))
        return self._dispatch(lambda: self._with_auth(self._clients))

    @http.route("/api/clients/<int:partner_id>/", type="http", auth="none", methods=["GET", "PUT", "PATCH"], cors="*", csrf=False)
    def client_detail(self, partner_id, **kwargs):
        if request.httprequest.method in {"PUT", "PATCH"}:
            return self._dispatch(lambda: self._with_auth(lambda: self._client_update(partner_id)))
        return self._dispatch(lambda: self._with_auth(lambda: self._client_detail(partner_id)))

    @http.route("/api/clients/<int:partner_id>/open-invoices/", type="http", auth="none", methods=["GET"], cors="*", csrf=False)
    def client_open_invoices(self, partner_id, **kwargs):
        return self._dispatch(lambda: self._with_auth(lambda: self._client_open_invoices(partner_id)))

    @http.route("/api/clients/<int:partner_id>/collections/", type="http", auth="none", methods=["POST"], cors="*", csrf=False)
    def client_collections(self, partner_id, **kwargs):
        return self._dispatch(lambda: self._with_auth(lambda: self._client_collection_create(partner_id)))

    @http.route("/api/clients/<int:partner_id>/location/", type="http", auth="none", methods=["POST"], cors="*", csrf=False)
    def client_update_location(self, partner_id, **kwargs):
        return self._dispatch(lambda: self._with_auth(lambda: self._client_update_location(partner_id)))

    @http.route("/api/mobile/device/register/", type="http", auth="none", methods=["POST"], cors="*", csrf=False)
    def register_device(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._register_device))

    @http.route("/api/notifications/", type="http", auth="none", methods=["GET"], cors="*", csrf=False)
    def notifications(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._notifications))

    @http.route("/api/notifications/read/", type="http", auth="none", methods=["POST"], cors="*", csrf=False)
    def notifications_read(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._notifications_read))

    def _with_auth(self, callback):
        self._authenticate()
        return callback()

    def _client_domain(self):
        domain = [("type", "!=", "private")]
        location_filter = (self._arg("location_filter") or "").strip()
        if location_filter == "with_location":
            domain.append(("ftiq_mobile_last_location_at", "!=", False))
        elif location_filter == "without_location":
            domain.append(("ftiq_mobile_last_location_at", "=", False))
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
            "address": self._field_value(partner, "contact_address_complete", "") or partner.contact_address or "",
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

    def _client_values(self, payload, create=False):
        name = (payload.get("name") or "").strip()
        if create and not name:
            return None, self._error(_("Client name is required."))
        values = {}
        if name:
            values["name"] = name
        for payload_key, field_name in (
            ("email", "email"),
            ("phone", "phone"),
            ("mobile", "mobile"),
            ("street", "street"),
            ("city", "city"),
            ("postcode", "zip"),
            ("job_title", "function"),
            ("notes", "comment"),
        ):
            if payload_key in payload:
                values[field_name] = (payload.get(payload_key) or "").strip()
        if "is_company" in payload:
            values["is_company"] = self._payload_bool(payload, "is_company", False)
        return values, None

    def _clients(self):
        limit, offset = self._limit_offset()
        Partner = request.env["res.partner"].with_context(active_test=False)
        domain = self._client_domain()
        client_filter = (self._arg("filter") or "all").strip()
        sort = (self._arg("sort") or "name").strip()
        if client_filter == "outstanding" or sort == "due_desc":
            all_partners = Partner.search(domain, order="name, id")
            all_metrics = self._invoice_metrics_by_partner(all_partners)
            partner_rows = []
            for partner in all_partners:
                commercial = partner.commercial_partner_id or partner
                metric = all_metrics.get(
                    commercial.id,
                    {"due_amount": 0.0, "open_invoice_count": 0},
                )
                if client_filter == "outstanding" and metric.get("due_amount", 0.0) <= 0:
                    continue
                partner_rows.append((partner, metric))
            if sort == "due_desc":
                partner_rows.sort(
                    key=lambda item: (item[1].get("due_amount", 0.0), item[0].display_name or ""),
                    reverse=True,
                )
            count = len(partner_rows)
            paged_rows = partner_rows[offset : offset + limit]
            partners = Partner.browse([row[0].id for row in paged_rows])
            metrics = {
                (row[0].commercial_partner_id or row[0]).id: row[1]
                for row in paged_rows
            }
        else:
            order = "create_date desc, id desc" if sort == "newest" else "name, id"
            count = Partner.search_count(domain)
            partners = Partner.search(domain, order=order, limit=limit, offset=offset)
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

    def _client_create(self):
        payload = self._json_body()
        values, error = self._client_values(payload, create=True)
        if error:
            return error
        partner = request.env["res.partner"].create(values)
        return self._json(self._serialize_client(partner), status=201)

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

    def _client_update(self, partner_id):
        partner = self._browse_client(partner_id)
        if not partner:
            return self._error(_("Client not found."), status=404)
        payload = self._json_body()
        values, error = self._client_values(payload)
        if error:
            return error
        if not values:
            return self._error(_("No client fields to update."))
        partner.write(values)
        commercial = partner.commercial_partner_id or partner
        metrics = self._invoice_metrics_by_partner(partner)
        return self._json(
            self._serialize_client(
                partner,
                metrics=metrics.get(commercial.id, {"due_amount": 0.0, "open_invoice_count": 0}),
                include_invoices=True,
            )
        )

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

    def _client_collection_create(self, partner_id):
        partner = self._browse_client(partner_id)
        if not partner:
            return self._error(_("Client not found."), status=404)
        payload = self._json_body()
        location = self._location_payload(payload)
        if not location:
            return self._error(_("Latitude and longitude are required."))

        request_uid = (payload.get("mobile_request_uid") or "").strip()
        if not request_uid:
            return self._error(_("mobile_request_uid is required."))

        Draft = request.env["ftiq.collection.draft"]
        existing = Draft.search([("mobile_request_uid", "=", request_uid)], limit=1)
        if existing:
            return self._json(
                {
                    "collection": self._serialize_collection_draft(existing),
                    "duplicate": True,
                }
            )

        invoices = self._client_invoices(partner)
        if not invoices:
            return self._error(_("This client has no open invoices."))

        requested_invoice_ids = []
        for item in payload.get("invoice_ids") or []:
            try:
                requested_invoice_ids.append(int(item))
            except Exception:
                continue
        if requested_invoice_ids:
            requested_set = set(requested_invoice_ids)
            invoices = invoices.filtered(lambda move: move.id in requested_set)
            if len(invoices) != len(requested_set):
                return self._error(_("One or more selected invoices are not open for this client."))

        currencies = invoices.mapped("currency_id")
        if len(currencies) > 1:
            return self._error(_("Collection drafts must use invoices with a single currency."))

        amount = self._payload_float(payload, "amount")
        residual = sum(invoices.mapped("amount_residual"))
        if amount is None or amount <= 0:
            return self._error(_("Collection amount must be greater than zero."))
        if amount > residual + 0.0001:
            return self._error(_("Collection amount cannot exceed the selected open invoice residual."))

        commercial = partner.commercial_partner_id or partner
        draft = Draft.create(
            {
                "partner_id": partner.id,
                "collector_id": request.env.user.id,
                "company_id": request.env.company.id,
                "currency_id": currencies[:1].id if currencies else request.env.company.currency_id.id,
                "invoice_ids": [(6, 0, invoices.ids)],
                "amount": amount,
                "payment_note": (payload.get("payment_note") or "").strip(),
                "mobile_request_uid": request_uid,
                "state": "submitted",
            }
        )
        self._apply_mobile_location(draft, payload, partner=commercial)
        attachment_ids = self._create_collection_attachments(draft, payload.get("attachments") or [])
        body = _("Mobile collection draft submitted from the field.")
        draft.message_post(body=body, attachment_ids=attachment_ids)
        return self._json(
            {
                "collection": self._serialize_collection_draft(draft),
                "message": _("Collection draft submitted successfully."),
            },
            status=201,
        )

    def _create_collection_attachments(self, draft, attachments):
        attachment_ids = []
        Attachment = request.env["ir.attachment"]
        for index, item in enumerate(attachments[:5], start=1):
            if not isinstance(item, dict):
                continue
            filename = (item.get("name") or item.get("filename") or "").strip()
            if not filename:
                filename = _("Collection attachment %s") % index
            data = (item.get("data") or item.get("datas") or "").strip()
            if "," in data and data.lower().startswith("data:"):
                data = data.split(",", 1)[1]
            if not data:
                continue
            try:
                decoded = base64.b64decode(data, validate=True)
            except Exception:
                raise ValidationError(_("Invalid attachment data."))
            if len(decoded) > 8 * 1024 * 1024:
                raise ValidationError(_("Attachment size cannot exceed 8 MB."))
            attachment = Attachment.create(
                {
                    "name": filename,
                    "datas": data,
                    "mimetype": (item.get("mimetype") or "application/octet-stream").strip(),
                    "res_model": draft._name,
                    "res_id": draft.id,
                }
            )
            attachment_ids.append(attachment.id)
        if attachment_ids:
            draft.write({"attachment_ids": [(6, 0, attachment_ids)]})
        return attachment_ids

    def _serialize_collection_draft(self, draft):
        return {
            "id": str(draft.id),
            "name": draft.name or "",
            "partner_id": str(draft.partner_id.id) if draft.partner_id else "",
            "partner_name": draft.partner_id.display_name if draft.partner_id else "",
            "collector_id": str(draft.collector_id.id) if draft.collector_id else "",
            "collector_name": draft.collector_id.name if draft.collector_id else "",
            "amount": draft.amount,
            "currency": draft.currency_id.name if draft.currency_id else request.env.company.currency_id.name,
            "state": draft.state,
            "mobile_request_uid": draft.mobile_request_uid or "",
            "submitted_at": self._date_string(draft.submitted_at),
            "invoice_ids": [str(move.id) for move in draft.invoice_ids],
            "attachments": [
                {
                    "id": str(attachment.id),
                    "name": attachment.name or "",
                    "mimetype": attachment.mimetype or "",
                }
                for attachment in draft.attachment_ids
            ],
            **self._record_mobile_location(draft),
        }

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
            "last_seen_at": fields.Datetime.now(),
            "last_registration_at": fields.Datetime.now(),
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
