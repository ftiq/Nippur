import base64
import json
import math
from pathlib import Path

from markupsafe import Markup, escape
from odoo import _, fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.osv import expression

from .base_api import FtiqCrmApiBase


class FtiqCrmMobileSupportApi(FtiqCrmApiBase):
    _CLIENT_CLASSIFICATION_PARAM_KEYS = (
        "ftiq_mobile_api.client_classification_field",
        "ftiq_mobile_api.partner_classification_field",
    )

    _CLIENT_CLASSIFICATION_KEYWORDS = (
        "classification",
        "class",
        "segment",
        "tier",
        "grade",
        "type",
        "category",
        "تصنيف",
        "فئة",
        "صنف",
        "شريحة",
        "درجة",
        "نوع",
    )

    @http.route("/api/clients/", type="http", auth="none", methods=["GET", "POST"], cors="*", csrf=False)
    def clients(self, **kwargs):
        if request.httprequest.method == "POST":
            return self._dispatch(lambda: self._with_auth(self._client_create))
        return self._dispatch(lambda: self._with_auth(self._clients))

    @http.route(
        ["/api/clients/address-options/", "/api/client-address-options/"],
        type="http",
        auth="none",
        methods=["GET"],
        cors="*",
        csrf=False,
    )
    def client_address_options(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._client_address_options))

    @http.route("/api/clients/filter-options/", type="http", auth="none", methods=["GET"], cors="*", csrf=False)
    def client_filter_options(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._client_filter_options))

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

    @http.route("/api/mobile/web-errors/", type="http", auth="none", methods=["POST", "OPTIONS"], cors="*", csrf=False)
    def web_errors(self, **kwargs):
        if request.httprequest.method == "OPTIONS":
            return request.make_response(
                "",
                headers=[
                    ("Access-Control-Allow-Origin", "*"),
                    ("Access-Control-Allow-Methods", "POST, OPTIONS"),
                    ("Access-Control-Allow-Headers", "Content-Type, Authorization"),
                ],
            )
        return self._dispatch(self._web_errors)

    def _with_auth(self, callback):
        self._authenticate()
        return callback()

    def _arg_float(self, key, default=None):
        value = self._arg(key)
        if value in (None, ""):
            return default
        try:
            return float(value)
        except Exception:
            return default

    def _nearby_filter_params(self):
        if (self._arg("location_filter") or "").strip() != "nearby":
            return None
        latitude = self._arg_float("nearby_latitude")
        longitude = self._arg_float("nearby_longitude")
        radius_meters = self._arg_float("nearby_radius_meters")
        if latitude is None or longitude is None or radius_meters is None:
            return None
        if radius_meters <= 0:
            return None
        return latitude, longitude, radius_meters

    def _distance_meters(self, latitude_a, longitude_a, latitude_b, longitude_b):
        earth_radius_meters = 6371000.0
        lat_a = math.radians(latitude_a)
        lat_b = math.radians(latitude_b)
        delta_lat = math.radians(latitude_b - latitude_a)
        delta_lng = math.radians(longitude_b - longitude_a)
        haversine = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lng / 2) ** 2
        )
        return earth_radius_meters * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))

    def _nearby_partner_rows(self, partners, latitude, longitude, radius_meters):
        rows = []
        for partner in partners:
            commercial = partner.commercial_partner_id or partner
            location = self._partner_mobile_location(commercial)
            partner_latitude = location.get("latitude")
            partner_longitude = location.get("longitude")
            if partner_latitude in (None, False) or partner_longitude in (None, False):
                continue
            try:
                distance = self._distance_meters(
                    latitude,
                    longitude,
                    float(partner_latitude),
                    float(partner_longitude),
                )
            except Exception:
                continue
            if distance <= radius_meters:
                rows.append((partner, distance))
        rows.sort(key=lambda item: (item[1], item[0].display_name or ""))
        return rows

    def _location_number_text(self, value):
        try:
            return ("%.6f" % float(value)).rstrip("0").rstrip(".")
        except Exception:
            return str(value or "")

    def _collection_location_chatter_body(self, location_values):
        latitude = self._location_number_text(location_values.get("ftiq_mobile_latitude"))
        longitude = self._location_number_text(location_values.get("ftiq_mobile_longitude"))
        accuracy = location_values.get("ftiq_mobile_accuracy")
        location_at = location_values.get("ftiq_mobile_location_at")
        location_at_text = fields.Datetime.to_string(location_at) if location_at else ""
        maps_url = "https://www.google.com/maps/search/?api=1&query=%s,%s" % (latitude, longitude)
        rows = [
            (_("Latitude"), latitude),
            (_("Longitude"), longitude),
        ]
        if accuracy not in (None, False):
            rows.append((_("Accuracy"), "%s %s" % (self._location_number_text(accuracy), _("m"))))
        if location_at_text:
            rows.append((_("Recorded At"), location_at_text))
        rows_html = "".join(
            "<tr><td class=\"ftiq-mobile-note__muted\" style=\"padding:3px 12px 3px 0;color:#6b7280;\">%s</td>"
            "<td style=\"padding:3px 0;font-weight:600;color:#111827;\">%s</td></tr>"
            % (escape(label), escape(value))
            for label, value in rows
        )
        mock_html = ""
        if location_values.get("ftiq_mobile_is_mock"):
            mock_html = (
                "<div class=\"ftiq-mobile-note__alert\" style=\"margin:8px 0;padding:6px 8px;border-radius:6px;"
                "background:#fff3cd;color:#8a5a00;font-weight:600;\">%s</div>"
                % escape(_("Mock location detected"))
            )
        return Markup(
            "<div class=\"ftiq-mobile-note\" style=\"border:1px solid #d8dee4;border-radius:8px;padding:12px;max-width:460px;background:#ffffff;color:#111827;\">"
            "<div class=\"ftiq-mobile-note__title\" style=\"font-weight:700;margin-bottom:8px;color:#111827;\">%s</div>"
            "<div class=\"ftiq-mobile-note__subtitle\" style=\"color:#374151;margin-bottom:8px;\">%s</div>"
            "<table class=\"ftiq-mobile-note__table\" style=\"border-collapse:collapse;margin-bottom:10px;\">%s</table>"
            "%s"
            "<a href=\"%s\" target=\"_blank\" rel=\"noopener noreferrer\" class=\"ftiq-mobile-note__action\" "
            "style=\"display:inline-block;padding:7px 12px;border:1px solid #0d6efd;"
            "border-radius:6px;color:#0d6efd;text-decoration:none;font-weight:700;\">%s</a>"
            "</div>"
            % (
                escape(_("Collection location")),
                escape(_("This location was captured by the mobile application during collection.")),
                rows_html,
                mock_html,
                escape(maps_url),
                escape(_("Open location in Google Maps")),
            )
        )

    def _client_domain(self):
        domain = [("type", "!=", "private")]
        location_filter = (self._arg("location_filter") or "").strip()
        if location_filter == "with_location":
            domain.append(("ftiq_mobile_last_location_at", "!=", False))
        elif location_filter == "nearby":
            domain.append(("partner_latitude", "!=", False))
            domain.append(("partner_longitude", "!=", False))
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
        classification_value = (self._arg("classification_value") or "").strip()
        classification_meta = self._client_classification_field_meta()
        if classification_value and classification_meta:
            field_name = classification_meta["name"]
            domain = expression.AND(
                [
                    domain,
                    [
                        "|",
                        (field_name, "=", classification_value),
                        ("commercial_partner_id.%s" % field_name, "=", classification_value),
                    ],
                ]
            )
        tag_ids = self._client_tag_filter_ids()
        if tag_ids:
            domain = expression.AND(
                [
                    domain,
                    [
                        "|",
                        ("category_id", "in", tag_ids),
                        ("commercial_partner_id.category_id", "in", tag_ids),
                    ],
                ]
            )
        country_ids = self._client_int_filter_ids("country_ids")
        if country_ids:
            country_domain = [
                "|",
                ("country_id", "in", country_ids),
                ("commercial_partner_id.country_id", "in", country_ids),
            ]
            default_country = (
                request.env.company.account_fiscal_country_id
                or request.env.company.country_id
                or request.env["res.country"]
            )
            if default_country and default_country.id in country_ids:
                country_domain = expression.OR(
                    [
                        country_domain,
                        [
                            "|",
                            ("country_id", "=", False),
                            ("commercial_partner_id.country_id", "=", False),
                        ],
                    ]
                )
            domain = expression.AND(
                [
                    domain,
                    country_domain,
                ]
            )
        state_ids = self._client_int_filter_ids("state_ids")
        if state_ids:
            domain = expression.AND(
                [
                    domain,
                    [
                        "|",
                        ("state_id", "in", state_ids),
                        ("commercial_partner_id.state_id", "in", state_ids),
                    ],
                ]
            )
        city_values = self._client_text_filter_values("city_values")
        if city_values:
            domain = expression.AND(
                [
                    domain,
                    [
                        "|",
                        ("city", "in", city_values),
                        ("commercial_partner_id.city", "in", city_values),
                    ],
                ]
            )
        return domain

    def _client_tag_filter_ids(self):
        return self._client_int_filter_ids("tag_ids", fallback_param="category_ids")

    def _client_int_filter_ids(self, param_name, fallback_param=None):
        raw_value = (self._arg(param_name) or "").strip()
        if not raw_value and fallback_param:
            raw_value = (self._arg(fallback_param) or "").strip()
        if not raw_value:
            return []
        record_ids = []
        for chunk in raw_value.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                record_ids.append(int(chunk))
            except Exception:
                continue
        return record_ids

    def _client_text_filter_values(self, param_name, fallback_param=None):
        raw_value = (self._arg(param_name) or "").strip()
        if not raw_value and fallback_param:
            raw_value = (self._arg(fallback_param) or "").strip()
        if not raw_value:
            return []
        if raw_value.startswith("["):
            try:
                parsed = json.loads(raw_value)
            except Exception:
                parsed = []
            values = []
            seen = set()
            for item in parsed if isinstance(parsed, list) else []:
                value = str(item).strip()
                if not value or value in seen:
                    continue
                seen.add(value)
                values.append(value)
            return values
        values = []
        seen = set()
        for chunk in raw_value.split(","):
            value = chunk.strip()
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values

    def _client_classification_field_meta(self):
        Partner = request.env["res.partner"].with_context(active_test=False)
        fields_meta = Partner.fields_get()
        partner_fields = Partner._fields
        configured_field_name = ""
        parameter_env = request.env["ir.config_parameter"].sudo()
        for key in self._CLIENT_CLASSIFICATION_PARAM_KEYS:
            value = (parameter_env.get_param(key) or "").strip()
            if value:
                configured_field_name = value
                candidate = self._client_classification_candidate_meta(
                    Partner, fields_meta, partner_fields, value
                )
                if candidate:
                    candidate["source"] = "configured"
                    return candidate

        manual_candidates = []
        keyword_candidates = []
        for field_name in fields_meta:
            candidate = self._client_classification_candidate_meta(
                Partner, fields_meta, partner_fields, field_name
            )
            if not candidate:
                continue
            if candidate["manual"]:
                manual_candidates.append(candidate)
            if candidate["keyword_match"]:
                keyword_candidates.append(candidate)

        if len(manual_candidates) == 1:
            candidate = dict(manual_candidates[0])
            candidate["source"] = "single_manual"
            return candidate

        if keyword_candidates:
            keyword_candidates.sort(
                key=lambda item: (
                    item["manual"],
                    item["used_count"],
                    item["option_count"],
                    item["name"],
                ),
                reverse=True,
            )
            candidate = dict(keyword_candidates[0])
            candidate["source"] = "keyword"
            return candidate

        return None

    def _client_classification_candidate_meta(self, Partner, fields_meta, partner_fields, field_name):
        if not field_name or field_name in {"type", "company_type", "followup_status"}:
            return None
        meta = fields_meta.get(field_name) or {}
        if meta.get("type") != "selection":
            return None
        options = meta.get("selection") or []
        if len(options) < 2:
            return None
        field = partner_fields.get(field_name)
        if not field or not getattr(field, "store", False):
            return None
        if not meta.get("searchable", True):
            return None
        used_count = 0
        try:
            used_count = Partner.search_count(
                [("customer_rank", ">", 0), (field_name, "!=", False)]
            )
        except Exception:
            used_count = 0
        keyword_match = self._client_classification_keyword_match(
            field_name, meta.get("string", ""), options
        )
        return {
            "name": field_name,
            "label": meta.get("string") or field_name,
            "options": [
                {
                    "value": value,
                    "label": label,
                }
                for value, label in options
                if value not in (None, "", False)
            ],
            "option_count": len(options),
            "used_count": used_count,
            "manual": bool(getattr(field, "manual", False)),
            "keyword_match": keyword_match,
        }

    def _client_classification_keyword_match(self, field_name, field_label, options):
        haystack = [field_name or "", field_label or ""]
        for value, label in options or []:
            haystack.append(str(value or ""))
            haystack.append(str(label or ""))
        haystack_text = " ".join(haystack).lower()
        return any(keyword in haystack_text for keyword in self._CLIENT_CLASSIFICATION_KEYWORDS)

    def _client_classification_value(self, partner, classification_meta):
        if not classification_meta or not classification_meta.get("name"):
            return "", ""
        field_name = classification_meta["name"]
        commercial = partner.commercial_partner_id or partner
        value = (
            self._field_value(commercial, field_name, "")
            or self._field_value(partner, field_name, "")
            or ""
        )
        label_map = {
            str(item.get("value")): item.get("label") or str(item.get("value"))
            for item in classification_meta.get("options") or []
        }
        return value, label_map.get(str(value), value or "")

    def _client_filter_options(self):
        classification_meta = self._client_classification_field_meta()
        classification_data = None
        if classification_meta and classification_meta.get("option_count"):
            classification_data = {
                "field_name": classification_meta["name"],
                "label": classification_meta["label"],
                "source": classification_meta.get("source") or "auto",
                "options": classification_meta.get("options") or [],
            }
        tags = request.env["res.partner.category"].search([], order="name, id")
        overdue_strategy = "partner_total_overdue" if "total_overdue" in request.env["res.partner"]._fields else "invoice_due_date"
        return self._json(
            {
                "classification": classification_data,
                "tags": [
                    {
                        "id": str(tag.id),
                        "name": tag.display_name or "",
                    }
                    for tag in tags
                ],
                "standard": {
                    "overdue_field": "total_overdue" if "total_overdue" in request.env["res.partner"]._fields else "",
                    "followup_status_field": "followup_status" if "followup_status" in request.env["res.partner"]._fields else "",
                    "followup_next_action_date_field": (
                        "followup_next_action_date"
                        if "followup_next_action_date" in request.env["res.partner"]._fields
                        else ""
                    ),
                    "overdue_strategy": overdue_strategy,
                },
            }
        )

    def _browse_client(self, partner_id):
        return (
            request.env["res.partner"]
            .with_context(active_test=False)
            .browse(partner_id)
            .exists()
        )

    def _mobile_task_from_payload(self, payload, partner, expected_type):
        task_id = payload.get("task_id") or payload.get("ftiq_mobile_task_id")
        if task_id in (None, "", False):
            return request.env["project.task"]
        try:
            task_id = int(task_id)
        except Exception as exc:
            raise ValidationError(_("Invalid task.")) from exc

        task = (
            request.env["project.task"]
            .with_context(active_test=False, fsm_mode=True)
            .browse(task_id)
            .exists()
        )
        if not task:
            raise ValidationError(_("Task not found."))
        task.check_access_rights("read")
        task.check_access_rule("read")

        task_type = self._field_value(task, "ftiq_mobile_task_type", "") or ""
        if task_type != expected_type:
            raise ValidationError(_("The selected task type does not match this operation."))

        task_partner = self._field_value(task, "partner_id")
        if task_partner:
            task_commercial = task_partner.commercial_partner_id or task_partner
            partner_commercial = partner.commercial_partner_id or partner
            if task_commercial.id != partner_commercial.id:
                raise ValidationError(_("The task client does not match this client."))
        return task

    def _mark_mobile_task_done(self, task):
        if not task:
            return
        values = {
            "ftiq_mobile_visit_state": "completed",
            "ftiq_mobile_completed_at": fields.Datetime.now(),
        }
        if "state" in task._fields:
            values["state"] = "1_done"
        task.with_context(ftiq_mobile_location_write=True).write(
            {key: value for key, value in values.items() if key in task._fields}
        )

    def _client_invoices(self, partner):
        commercial_partner = partner.commercial_partner_id or partner
        if not commercial_partner or not self._has_model("account.move"):
            return request.env["account.move"]
        return request.env["account.move"].search(
            self._open_invoice_domain(commercial_partner.ids),
            order="invoice_date_due asc, invoice_date asc, id desc",
        )

    def _serialize_client(self, partner, metrics=None, include_invoices=False, classification_meta=None):
        commercial = partner.commercial_partner_id or partner
        location = self._partner_mobile_location(commercial)
        metrics = metrics or {
            "due_amount": 0.0,
            "open_invoice_count": 0,
            "currency": "",
            "overdue_amount": 0.0,
            "overdue_invoice_count": 0,
        }
        invoices = self._client_invoices(partner) if include_invoices else request.env["account.move"]
        collection_options = (
            self._build_collection_options(partner, invoices)
            if include_invoices
            else None
        )
        classification_meta = classification_meta or self._client_classification_field_meta()
        classification_value, classification_label = self._client_classification_value(
            partner, classification_meta
        )
        display_currency = (
            metrics.get("currency")
            or (collection_options.get("currency") if collection_options else "")
            or (
                commercial.company_id.currency_id.name
                if commercial.company_id and commercial.company_id.currency_id
                else request.env.company.currency_id.name
            )
        )
        return {
            "id": str(partner.id),
            "commercial_partner_id": str(commercial.id),
            "name": partner.display_name,
            "display_name": partner.display_name,
            "email": partner.email or "",
            "phone": partner.phone or "",
            "mobile": partner.mobile or "",
            "street": partner.street or "",
            "street2": partner.street2 or "",
            "city": partner.city or "",
            "state_id": str(partner.state_id.id) if partner.state_id else "",
            "state": partner.state_id.name if partner.state_id else "",
            "country_id": str(partner.country_id.id) if partner.country_id else "",
            "country": partner.country_id.name if partner.country_id else "",
            "postcode": partner.zip or "",
            "address": self._field_value(partner, "contact_address_complete", "") or partner.contact_address or "",
            "parent_name": partner.parent_id.display_name if partner.parent_id else "",
            "job_title": partner.function or "",
            "notes": partner.comment or "",
            "is_company": bool(partner.is_company),
            "due_amount": metrics.get("due_amount", 0.0),
            "open_invoice_count": metrics.get("open_invoice_count", 0),
            "overdue_amount": metrics.get("overdue_amount", 0.0),
            "overdue_invoice_count": metrics.get("overdue_invoice_count", 0),
            "is_overdue": metrics.get("overdue_amount", 0.0) > 0,
            "currency": display_currency,
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "location_accuracy": location["accuracy"],
            "location_is_mock": location["is_mock"],
            "location_at": location["location_at"],
            "tags": [
                tag.display_name
                for tag in ((commercial.category_id or partner.category_id) or request.env["res.partner.category"])
            ],
            "classification_field": classification_meta.get("name") if classification_meta else "",
            "classification_field_label": classification_meta.get("label") if classification_meta else "",
            "classification": classification_value or "",
            "classification_label": classification_label or "",
            "followup_status": self._field_value(commercial, "followup_status", "") or "",
            "followup_next_action_date": self._date_string(
                self._field_value(commercial, "followup_next_action_date")
            ),
            "total_due": self._field_value(commercial, "total_due", metrics.get("due_amount", 0.0))
            or metrics.get("due_amount", 0.0),
            "total_overdue": self._field_value(
                commercial, "total_overdue", metrics.get("overdue_amount", 0.0)
            )
            or metrics.get("overdue_amount", 0.0),
            "open_invoices": [
                self._serialize_invoice_summary(move)
                for move in (invoices if include_invoices else request.env["account.move"])
            ],
            "collection_options": collection_options,
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
            ("street2", "street2"),
            ("city", "city"),
            ("postcode", "zip"),
            ("job_title", "function"),
            ("notes", "comment"),
        ):
            if payload_key in payload:
                values[field_name] = (payload.get(payload_key) or "").strip()
        country, error = self._client_many2one_value(payload, "country_id", "res.country", _("Country"))
        if error:
            return None, error
        if country is not None:
            values["country_id"] = country.id if country else False
        state, error = self._client_many2one_value(payload, "state_id", "res.country.state", _("State"))
        if error:
            return None, error
        if state is not None:
            country_id = values.get("country_id")
            target_country_id = country_id if country_id is not False else False
            if state and target_country_id and state.country_id and state.country_id.id != target_country_id:
                return None, self._error(_("State does not belong to the selected country."))
            values["state_id"] = state.id if state else False
        if "is_company" in payload:
            values["is_company"] = self._payload_bool(payload, "is_company", False)
        return values, None

    def _client_many2one_value(self, payload, payload_key, model_name, label):
        if payload_key not in payload:
            return None, None
        raw_value = payload.get(payload_key)
        if raw_value in (None, "", False):
            return False, None
        try:
            record_id = int(raw_value)
        except Exception:
            return None, self._error(_("%s is invalid.") % label)
        record = request.env[model_name].browse(record_id).exists()
        if not record:
            return None, self._error(_("%s was not found.") % label)
        return record, None

    def _client_address_options(self):
        company = request.env.company
        default_country = (
            company.account_fiscal_country_id
            or company.country_id
            or request.env["res.country"]
        )
        countries = request.env["res.country"].search([], order="name, id")
        states = request.env["res.country.state"].search([], order="name, id")
        city_rows = request.env["res.partner"].read_group(
            [("type", "!=", "private"), ("city", "!=", False)],
            ["city", "country_id", "state_id"],
            ["city", "country_id", "state_id"],
            orderby="city",
            lazy=False,
        )
        return self._json(
            {
                "default_country_id": str(default_country.id) if default_country else "",
                "default_country_name": default_country.name if default_country else "",
                "countries": [
                    {
                        "id": str(country.id),
                        "name": country.name or "",
                        "code": country.code or "",
                    }
                    for country in countries
                ],
                "states": [
                    {
                        "id": str(state.id),
                        "name": state.name or "",
                        "code": state.code or "",
                        "country_id": str(state.country_id.id) if state.country_id else "",
                        "country_name": state.country_id.name if state.country_id else "",
                    }
                    for state in states
                ],
                "cities": [
                    {
                        "id": row.get("city") or "",
                        "name": row.get("city") or "",
                        "code": "",
                        "country_id": str(row["country_id"][0]) if row.get("country_id") else "",
                        "country_name": row["country_id"][1] if row.get("country_id") else "",
                        "state_id": str(row["state_id"][0]) if row.get("state_id") else "",
                        "state_name": row["state_id"][1] if row.get("state_id") else "",
                    }
                    for row in city_rows
                    if row.get("city")
                ],
            }
        )

    def _clients(self):
        limit, offset = self._limit_offset()
        Partner = request.env["res.partner"].with_context(active_test=False)
        domain = self._client_domain()
        client_filter = (self._arg("filter") or "all").strip()
        sort = (self._arg("sort") or "name").strip()
        location_filter = (self._arg("location_filter") or "").strip()
        classification_meta = self._client_classification_field_meta()
        nearby_params = self._nearby_filter_params()
        use_nearby_filter = location_filter == "nearby"
        if use_nearby_filter or client_filter in {"outstanding", "overdue"} or sort in {"due_desc", "overdue_desc"}:
            all_partners = Partner.search(domain, order="name, id")
            if use_nearby_filter:
                if nearby_params:
                    nearby_rows = self._nearby_partner_rows(all_partners, *nearby_params)
                else:
                    nearby_rows = []
                all_partners = Partner.browse([row[0].id for row in nearby_rows])
                distance_by_partner_id = {row[0].id: row[1] for row in nearby_rows}
            else:
                distance_by_partner_id = {}
            all_metrics = self._invoice_metrics_by_partner(all_partners)
            partner_rows = []
            for partner in all_partners:
                commercial = partner.commercial_partner_id or partner
                metric = all_metrics.get(
                    commercial.id,
                    {
                        "due_amount": 0.0,
                        "open_invoice_count": 0,
                        "overdue_amount": 0.0,
                        "overdue_invoice_count": 0,
                    },
                )
                if client_filter == "outstanding" and metric.get("due_amount", 0.0) <= 0:
                    continue
                if client_filter == "overdue" and metric.get("overdue_amount", 0.0) <= 0:
                    continue
                partner_rows.append((partner, metric, distance_by_partner_id.get(partner.id)))
            if sort == "due_desc":
                partner_rows.sort(
                    key=lambda item: (item[1].get("due_amount", 0.0), item[0].display_name or ""),
                    reverse=True,
                )
            elif sort == "overdue_desc":
                partner_rows.sort(
                    key=lambda item: (item[1].get("overdue_amount", 0.0), item[0].display_name or ""),
                    reverse=True,
                )
            elif use_nearby_filter:
                partner_rows.sort(
                    key=lambda item: (
                        item[2] is None,
                        item[2] or 0.0,
                        item[0].display_name or "",
                    )
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
                            {
                                "due_amount": 0.0,
                                "open_invoice_count": 0,
                                "overdue_amount": 0.0,
                                "overdue_invoice_count": 0,
                            },
                        ),
                        classification_meta=classification_meta,
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
        return self._json(
            self._serialize_client(
                partner, classification_meta=self._client_classification_field_meta()
            ),
            status=201,
        )

    def _client_detail(self, partner_id):
        partner = self._browse_client(partner_id)
        if not partner:
            return self._error(_("Client not found."), status=404)
        commercial = partner.commercial_partner_id or partner
        metrics = self._invoice_metrics_by_partner(partner)
        data = self._serialize_client(
            partner,
            metrics=metrics.get(
                commercial.id,
                {
                    "due_amount": 0.0,
                    "open_invoice_count": 0,
                    "overdue_amount": 0.0,
                    "overdue_invoice_count": 0,
                },
            ),
            include_invoices=True,
            classification_meta=self._client_classification_field_meta(),
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
                metrics=metrics.get(
                    commercial.id,
                    {
                        "due_amount": 0.0,
                        "open_invoice_count": 0,
                        "overdue_amount": 0.0,
                        "overdue_invoice_count": 0,
                    },
                ),
                include_invoices=True,
                classification_meta=self._client_classification_field_meta(),
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

        collection_task = self._mobile_task_from_payload(payload, partner, "collection")
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
            return self._error(_("Selected invoices must use a single currency."))

        amount = self._payload_float(payload, "amount")
        cash_discount = self._payload_float(payload, "cash_discount", 0.0) or 0.0
        residual = sum(invoices.mapped("amount_residual"))
        if amount is None or amount <= 0:
            return self._error(_("Collection amount must be greater than zero."))
        if amount > residual + 0.0001:
            return self._error(_("Collection amount cannot exceed the selected open invoice residual."))
        if cash_discount < 0:
            return self._error(_("Cash discount cannot be negative."))
        if cash_discount > 0 and abs((amount + cash_discount) - residual) > 0.0001:
            return self._error(
                _("When a cash discount is used, the collection amount plus cash discount must match the selected open invoice residual.")
            )

        commercial = partner.commercial_partner_id or partner
        payment_date = (payload.get("payment_date") or "").strip() or fields.Date.context_today(request.env.user)
        note = (payload.get("payment_note") or payload.get("memo") or "").strip()
        wizard = self._prepare_collection_wizard(
            invoices,
            amount=amount,
            payment_date=payment_date,
            communication=note,
            journal_id=payload.get("journal_id"),
            payment_method_line_id=payload.get("payment_method_line_id"),
        )
        if cash_discount > 0:
            discount_account = self._cash_discount_account()
            if not discount_account:
                return self._error(_("Cash discount account is not configured."))
            if "cash_discount" in wizard._fields and "discount_account_id" in wizard._fields:
                wizard.write(
                    {
                        "amount": amount,
                        "cash_discount": cash_discount,
                        "discount_account_id": discount_account.id,
                    }
                )
            else:
                wizard.write(
                    {
                        "amount": amount,
                        "payment_difference_handling": "reconcile",
                        "writeoff_account_id": discount_account.id,
                        "writeoff_label": self._payment_cash_discount_label() or _("Cash Discount"),
                    }
                )
        payments = wizard._create_payments()
        if not payments:
            return self._error(_("No payment was created."))

        location_body = self._collection_location_chatter_body(location)
        for payment in payments:
            if collection_task and "ftiq_mobile_task_id" in payment._fields:
                payment.ftiq_mobile_task_id = collection_task.id
            if cash_discount > 0 and self._payment_supports_cash_discount():
                payment.write({"cash_discount": cash_discount})
            self._apply_mobile_location(payment, payload, partner=commercial)
            attachment_ids = self._create_record_attachments(payment, payload.get("attachments") or [])
            payment.message_post(
                body=location_body,
                attachment_ids=attachment_ids,
            )
            if collection_task:
                collection_task.message_post(
                    body=Markup(
                        "<p>%s</p>"
                        % escape(
                            _("Collection payment created from the mobile application: %s")
                            % (payment.display_name or payment.name or payment.id)
                        )
                    )
                )
        self._mark_mobile_task_done(collection_task)
        for invoice in invoices:
            invoice.message_post(body=location_body)
        return self._json(
            {
                "payment": self._serialize_collection_payment(payments[0], invoices, request_uid),
                "payments": [
                    self._serialize_collection_payment(payment, invoices, request_uid)
                    for payment in payments
                ],
                "duplicate": False,
                "message": _("Collection recorded successfully."),
            },
            status=201,
        )

    def _build_collection_options(self, partner, invoices):
        supports_cash_discount = self._payment_supports_cash_discount()
        cash_discount_label = self._payment_cash_discount_label() if supports_cash_discount else ""
        if not invoices:
            return {
                "currency": request.env.company.currency_id.name,
                "amount_by_default": 0.0,
                "full_amount": 0.0,
                "selected_journal_id": "",
                "selected_payment_method_line_id": "",
                "journals": [],
                "payment_method_lines": [],
                "allow_attachments": True,
                "requires_partner_bank_account": False,
                "can_register_payment": False,
                "supports_cash_discount": supports_cash_discount,
                "cash_discount_label": cash_discount_label,
                "default_cash_discount": 0.0,
                "blocking_message": _("This client has no open invoices."),
            }
        try:
            wizard = self._prepare_collection_wizard(invoices)
        except (UserError, ValidationError) as exc:
            currency = (
                invoices[:1].currency_id.name
                if invoices[:1] and invoices[:1].currency_id
                else request.env.company.currency_id.name
            )
            return {
                "currency": currency,
                "amount_by_default": sum(invoices.mapped("amount_residual")),
                "full_amount": sum(invoices.mapped("amount_residual")),
                "selected_journal_id": "",
                "selected_payment_method_line_id": "",
                "journals": [],
                "payment_method_lines": [],
                "allow_attachments": True,
                "requires_partner_bank_account": False,
                "can_register_payment": False,
                "supports_cash_discount": supports_cash_discount,
                "cash_discount_label": cash_discount_label,
                "default_cash_discount": 0.0,
                "blocking_message": str(exc),
            }
        journals = wizard.available_journal_ids.sorted(lambda journal: (journal.sequence, journal.name or "", journal.id))
        payment_method_lines = []
        current_journal = wizard.journal_id
        current_payment_method_line = wizard.payment_method_line_id
        for journal in journals:
            wizard.journal_id = journal._origin
            for line in wizard.available_payment_method_line_ids.sorted(
                lambda item: (item.sequence, item.name or "", item.id)
            ):
                payment_method_lines.append(
                    {
                        "id": str(line.id),
                        "name": line.name,
                        "journal_id": str(journal.id),
                        "code": line.code,
                    }
                )
        wizard.journal_id = current_journal._origin
        wizard.payment_method_line_id = current_payment_method_line._origin
        return {
            "currency": wizard.currency_id.name if wizard.currency_id else request.env.company.currency_id.name,
            "amount_by_default": wizard.amount,
            "full_amount": sum(invoices.mapped("amount_residual")),
            "selected_journal_id": str(wizard.journal_id._origin.id) if wizard.journal_id else "",
            "selected_payment_method_line_id": str(wizard.payment_method_line_id._origin.id) if wizard.payment_method_line_id else "",
            "journals": [
                {
                    "id": str(journal.id),
                    "name": journal.display_name,
                    "type": journal.type,
                }
                for journal in journals
            ],
            "payment_method_lines": [
                line for line in payment_method_lines
            ],
            "allow_attachments": True,
            "requires_partner_bank_account": bool(wizard.require_partner_bank_account),
            "can_register_payment": bool(journals),
            "supports_cash_discount": supports_cash_discount,
            "cash_discount_label": cash_discount_label,
            "default_cash_discount": 0.0,
            "blocking_message": "" if journals else _("No payment journal is available for this customer."),
        }

    def _payment_supports_cash_discount(self):
        return "cash_discount" in request.env["account.payment"]._fields

    def _payment_cash_discount_label(self):
        field = request.env["ir.model.fields"].sudo().search(
            [("model", "=", "account.payment"), ("name", "=", "cash_discount")],
            limit=1,
        )
        return field.field_description or _("Cash Discount")

    def _prepare_collection_wizard(
        self,
        invoices,
        amount=None,
        payment_date=None,
        communication="",
        journal_id=None,
        payment_method_line_id=None,
    ):
        Wizard = request.env["account.payment.register"].with_context(
            active_model="account.move",
            active_ids=invoices.ids,
        )
        wizard = Wizard.create(
            {
                "group_payment": len(invoices) > 1,
            }
        )
        if not wizard.available_journal_ids:
            raise ValidationError(_("No payment journal is available for this customer."))

        if journal_id not in (None, ""):
            try:
                journal_id = int(journal_id)
            except Exception as exc:
                raise ValidationError(_("Invalid payment journal.")) from exc
            journal = wizard.available_journal_ids.filtered(lambda item: item.id == journal_id)[:1]
            if not journal:
                raise ValidationError(_("The selected payment journal is not available for this customer."))
            wizard.journal_id = journal._origin
        elif not wizard.journal_id and wizard.available_journal_ids:
            wizard.journal_id = wizard.available_journal_ids[:1]._origin
        elif wizard.journal_id:
            wizard.journal_id = wizard.journal_id._origin

        if payment_date:
            wizard.payment_date = payment_date
        if communication:
            wizard.communication = communication

        available_lines = wizard.available_payment_method_line_ids
        if payment_method_line_id not in (None, ""):
            try:
                payment_method_line_id = int(payment_method_line_id)
            except Exception as exc:
                raise ValidationError(_("Invalid payment method.")) from exc
            payment_method_line = available_lines.filtered(lambda item: item.id == payment_method_line_id)[:1]
            if not payment_method_line:
                raise ValidationError(_("The selected payment method is not available for the chosen journal."))
            wizard.payment_method_line_id = payment_method_line._origin
        elif not wizard.payment_method_line_id and available_lines:
            wizard.payment_method_line_id = available_lines[:1]._origin
        elif wizard.payment_method_line_id:
            wizard.payment_method_line_id = wizard.payment_method_line_id._origin

        if not wizard.payment_method_line_id:
            raise ValidationError(_("No inbound payment method is configured for the selected journal."))

        if amount is not None:
            wizard.amount = amount

        return wizard

    def _cash_discount_account(self):
        if not self._payment_supports_cash_discount():
            return request.env["account.account"]
        defaults = request.env["account.payment"].default_get(["discount_account_id"])
        account_id = defaults.get("discount_account_id")
        if account_id:
            return request.env["account.account"].browse(account_id).exists()
        recent_payment = request.env["account.payment"].search(
            [("discount_account_id", "!=", False)],
            order="id desc",
            limit=1,
        )
        return recent_payment.discount_account_id if recent_payment else request.env["account.account"]

    def _create_record_attachments(self, record, attachments):
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
                    "res_model": record._name,
                    "res_id": record.id,
                }
            )
            attachment_ids.append(attachment.id)
        return attachment_ids

    def _serialize_collection_payment(self, payment, invoices, request_uid):
        return {
            "id": str(payment.id),
            "name": payment.name or "",
            "partner_id": str(payment.partner_id.id) if payment.partner_id else "",
            "partner_name": payment.partner_id.display_name if payment.partner_id else "",
            "amount": payment.amount,
            "currency": payment.currency_id.name if payment.currency_id else request.env.company.currency_id.name,
            "state": payment.state,
            "date": self._date_string(payment.date),
            "journal": {
                "id": str(payment.journal_id.id) if payment.journal_id else "",
                "name": payment.journal_id.display_name if payment.journal_id else "",
            },
            "payment_method": {
                "id": str(payment.payment_method_line_id.id) if payment.payment_method_line_id else "",
                "name": payment.payment_method_line_id.name if payment.payment_method_line_id else "",
            },
            "memo": payment.memo or "",
            "cash_discount": self._field_value(payment, "cash_discount", 0.0) or 0.0,
            "mobile_request_uid": request_uid,
            "task_id": str(self._field_value(payment, "ftiq_mobile_task_id").id)
            if self._field_value(payment, "ftiq_mobile_task_id")
            else "",
            "invoice_ids": [str(move.id) for move in invoices],
            "invoice_numbers": [
                move.name or move.display_name or ""
                for move in invoices
            ],
            **self._record_mobile_location(payment),
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
        partner_id = request.env.user.partner_id.id
        domain = [
            ("res_partner_id", "=", partner_id),
            ("mail_message_id", "!=", False),
            ("mail_message_id.model", "=", "project.task"),
            ("mail_message_id.author_id", "!=", partner_id),
            ("mail_message_id.create_uid.partner_id", "!=", partner_id),
        ]
        if self._arg("unread_only") in {"1", "true", "True"}:
            domain.append(("is_read", "=", False))
        return domain

    def _notifications(self):
        limit = max(1, min(self._arg_int("limit", 40), 100))
        search_limit = max(limit * 5, limit)
        notifications = request.env["mail.notification"].sudo().search(
            self._notification_domain(),
            order="id desc",
            limit=search_limit,
        ).filtered(
            lambda notification: not notification._ftiq_skip_mobile_push()
        )[:limit]
        unread_notifications = request.env["mail.notification"].sudo().search(
            [
                ("res_partner_id", "=", request.env.user.partner_id.id),
                ("mail_message_id", "!=", False),
                ("mail_message_id.model", "=", "project.task"),
                ("mail_message_id.author_id", "!=", request.env.user.partner_id.id),
                ("mail_message_id.create_uid.partner_id", "!=", request.env.user.partner_id.id),
                ("is_read", "=", False),
            ]
        ).filtered(
            lambda notification: not notification._ftiq_skip_mobile_push()
        )
        return self._json(
            {
                "items": [self._serialize_mail_notification(notification) for notification in notifications],
                "count": len(notifications),
                "unread_count": len(unread_notifications),
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

    def _web_errors(self):
        payload = self._json_body()
        level = (payload.get("level") or "error").strip().lower()
        if level != "error":
            return self._json({"error": False, "ignored": True})

        project_root = Path(__file__).resolve().parents[2]
        log_path = project_root / "mobile_web_errors.log"
        entry = {
            "timestamp": fields.Datetime.now().isoformat(),
            "level": level,
            "category": (payload.get("category") or "web").strip() or "web",
            "message": (payload.get("message") or "").strip(),
            "stack": (payload.get("stack") or "").strip(),
            "url": (payload.get("url") or "").strip(),
            "endpoint": (payload.get("endpoint") or "").strip(),
            "method": (payload.get("method") or "").strip(),
            "status_code": payload.get("status_code"),
            "details": (payload.get("details") or "").strip(),
            "user_agent": (payload.get("user_agent") or "").strip(),
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return self._json({"error": False, "logged": True})
