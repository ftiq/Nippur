from collections import OrderedDict

from odoo import _, fields, http
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request
from odoo.osv import expression

from .base_api import FtiqCrmApiBase


class FtiqCrmMobileSalesApi(FtiqCrmApiBase):
    @http.route(
        "/api/clients/<int:partner_id>/sales-order-options/",
        type="http",
        auth="none",
        methods=["GET"],
        cors="*",
        csrf=False,
    )
    def client_sales_order_options(self, partner_id, **kwargs):
        return self._dispatch(
            lambda: self._with_auth(
                lambda: self._client_sales_order_options(partner_id)
            )
        )

    @http.route(
        "/api/clients/<int:partner_id>/sale-orders/",
        type="http",
        auth="none",
        methods=["GET", "POST"],
        cors="*",
        csrf=False,
    )
    def client_sale_orders(self, partner_id, **kwargs):
        if request.httprequest.method == "POST":
            return self._dispatch(
                lambda: self._with_auth(
                    lambda: self._client_sale_order_create(partner_id)
                )
            )
        return self._dispatch(
            lambda: self._with_auth(lambda: self._client_sale_orders(partner_id))
        )

    @http.route(
        "/api/sale-orders/<int:order_id>/",
        type="http",
        auth="none",
        methods=["GET", "PATCH"],
        cors="*",
        csrf=False,
    )
    def sale_order_detail(self, order_id, **kwargs):
        if request.httprequest.method == "PATCH":
            return self._dispatch(
                lambda: self._with_auth(lambda: self._sale_order_update(order_id))
            )
        return self._dispatch(
            lambda: self._with_auth(lambda: self._sale_order_detail(order_id))
        )

    @http.route(
        "/api/sale-orders/<int:order_id>/confirm/",
        type="http",
        auth="none",
        methods=["POST"],
        cors="*",
        csrf=False,
    )
    def sale_order_confirm(self, order_id, **kwargs):
        return self._dispatch(
            lambda: self._with_auth(lambda: self._sale_order_confirm(order_id))
        )

    @http.route(
        "/api/sales/products/",
        type="http",
        auth="none",
        methods=["GET"],
        cors="*",
        csrf=False,
    )
    def sales_products(self, **kwargs):
        return self._dispatch(lambda: self._with_auth(self._sales_products))

    def _with_auth(self, callback):
        self._authenticate()
        return callback()

    def _ensure_sales_models(self):
        required_models = [
            "sale.order",
            "sale.order.line",
            "product.product",
        ]
        missing = [name for name in required_models if not self._has_model(name)]
        if missing:
            raise ValidationError(
                _("Sales order functionality is not available on this server.")
            )

    def _client_record(self, partner_id):
        self._ensure_sales_models()
        Partner = request.env["res.partner"].with_context(active_test=False)
        Partner.check_access_rights("read")
        return Partner.search([("id", "=", partner_id)], limit=1)

    def _sales_partner_for_client(self, partner):
        return partner.commercial_partner_id or partner

    def _default_warehouse_for_partner(self, partner):
        commercial = self._sales_partner_for_client(partner)
        if (
            "x_studio_warehouse" in commercial._fields
            and commercial.x_studio_warehouse
        ):
            return commercial.x_studio_warehouse
        if not self._has_model("stock.warehouse"):
            return request.env["stock.warehouse"]
        return request.env["stock.warehouse"].search([], limit=1)

    def _partner_sale_warning(self, partner):
        warning_partner = partner
        if warning_partner.sale_warn == "no-message" and warning_partner.parent_id:
            warning_partner = warning_partner.parent_id
        if warning_partner.sale_warn and warning_partner.sale_warn != "no-message":
            if (
                warning_partner.sale_warn != "block"
                and warning_partner.parent_id
                and warning_partner.parent_id.sale_warn == "block"
            ):
                warning_partner = warning_partner.parent_id
            return {
                "message": warning_partner.sale_warn_msg or "",
                "is_blocking": warning_partner.sale_warn == "block",
            }
        return {"message": "", "is_blocking": False}

    def _product_sale_warning(self, product):
        return {
            "message": product.sale_line_warn_msg or "",
            "is_blocking": product.sale_line_warn == "block",
        }

    def _draft_sale_order(self, partner):
        commercial = self._sales_partner_for_client(partner)
        order = request.env["sale.order"].new(
            {
                "partner_id": commercial.id,
                "company_id": request.env.company.id,
                "user_id": request.env.user.id,
            }
        )
        order._compute_partner_invoice_id()
        order._compute_partner_shipping_id()
        order._compute_payment_term_id()
        order._compute_pricelist_id()
        order._compute_user_id()
        order._compute_team_id()
        order._compute_partner_credit_warning()
        warehouse = self._default_warehouse_for_partner(commercial)
        if warehouse:
            order.warehouse_id = warehouse
        return order

    def _sales_user_scope(self):
        user = request.env.user
        if user.has_group("sales_team.group_sale_manager"):
            return "admin"
        if user.has_group("sales_team.group_sale_salesman_all_leads"):
            return "all"
        if user.has_group("sales_team.group_sale_salesman"):
            return "own"
        return "none"

    def _can_record_write(self, record):
        if not record:
            return False
        try:
            record.check_access_rule("write")
        except AccessError:
            return False
        return record.check_access_rights("write", raise_exception=False)

    def _serialize_sales_order_options(self, partner):
        SaleOrder = request.env["sale.order"]
        can_create = SaleOrder.check_access_rights("create", raise_exception=False)
        can_write = SaleOrder.check_access_rights("write", raise_exception=False)
        order = self._draft_sale_order(partner)
        partner_warning = self._partner_sale_warning(self._sales_partner_for_client(partner))
        blocking_message = ""
        if partner_warning["is_blocking"]:
            blocking_message = partner_warning["message"]
            can_create = False
        elif not can_create:
            blocking_message = _("You do not have permission to create sales orders.")
        return {
            "can_create": bool(can_create),
            "can_confirm": bool(can_create and can_write),
            "can_send": False,
            "user_scope": self._sales_user_scope(),
            "client_id": str(partner.id),
            "order_partner_id": str((self._sales_partner_for_client(partner)).id),
            "currency": order.currency_id.name if order.currency_id else request.env.company.currency_id.name,
            "default_pricelist_id": str(order.pricelist_id.id) if order.pricelist_id else "",
            "default_pricelist_name": order.pricelist_id.display_name if order.pricelist_id else "",
            "default_payment_term_id": str(order.payment_term_id.id) if order.payment_term_id else "",
            "default_payment_term_name": order.payment_term_id.display_name if order.payment_term_id else "",
            "default_warehouse_id": str(order.warehouse_id.id) if order.warehouse_id else "",
            "default_warehouse_name": order.warehouse_id.display_name if order.warehouse_id else "",
            "default_salesperson_id": str(order.user_id.id) if order.user_id else "",
            "default_salesperson_name": order.user_id.display_name if order.user_id else "",
            "default_team_id": str(order.team_id.id) if order.team_id else "",
            "default_team_name": order.team_id.display_name if order.team_id else "",
            "partner_warning": partner_warning["message"],
            "partner_credit_warning": order.partner_credit_warning or "",
            "blocking_message": blocking_message,
        }

    def _client_sales_order_options(self, partner_id):
        partner = self._client_record(partner_id)
        if not partner:
            return self._error(_("Client not found."), status=404)
        return self._json(self._serialize_sales_order_options(partner))

    def _order_domain_for_client(self, partner):
        commercial = self._sales_partner_for_client(partner)
        return [("partner_id.commercial_partner_id", "=", commercial.id)]

    def _state_label(self, order):
        state_selection = dict(order._fields["state"].selection)
        return state_selection.get(order.state, order.state or "")

    def _serialize_sales_order_line(self, line):
        product = line.product_id
        return {
            "id": str(line.id),
            "product_id": str(product.id) if product else "",
            "product_name": product.display_name if product else "",
            "default_code": product.default_code or "" if product else "",
            "barcode": product.barcode or "" if product else "",
            "description": line.name or "",
            "quantity": line.product_uom_qty or 0.0,
            "uom_name": line.product_uom.name if line.product_uom else "",
            "unit_price": line.price_unit or 0.0,
            "subtotal": line.price_subtotal or 0.0,
            "total": line.price_total or 0.0,
            "currency": line.order_id.currency_id.name if line.order_id.currency_id else "",
        }

    def _serialize_sales_order(self, order):
        can_confirm = (
            order.state in {"draft", "sent"}
            and bool(order.order_line.filtered(lambda line: not line.display_type))
            and self._can_record_write(order)
        )
        return {
            "id": str(order.id),
            "name": order.name or "",
            "state": order.state or "",
            "state_label": self._state_label(order),
            "partner_id": str(order.partner_id.id) if order.partner_id else "",
            "partner_name": order.partner_id.display_name if order.partner_id else "",
            "commercial_partner_id": str(order.partner_id.commercial_partner_id.id)
            if order.partner_id and order.partner_id.commercial_partner_id
            else "",
            "currency": order.currency_id.name if order.currency_id else "",
            "currency_symbol": order.currency_id.symbol if order.currency_id else "",
            "amount_untaxed": order.amount_untaxed or 0.0,
            "amount_tax": order.amount_tax or 0.0,
            "amount_total": order.amount_total or 0.0,
            "date_order": fields.Datetime.to_string(order.date_order)
            if order.date_order
            else "",
            "validity_date": fields.Date.to_string(order.validity_date)
            if order.validity_date
            else "",
            "note": order.note or "",
            "client_order_ref": order.client_order_ref or "",
            "pricelist_name": order.pricelist_id.display_name if order.pricelist_id else "",
            "payment_term_name": order.payment_term_id.display_name if order.payment_term_id else "",
            "warehouse_name": order.warehouse_id.display_name if order.warehouse_id else "",
            "salesperson_name": order.user_id.display_name if order.user_id else "",
            "team_name": order.team_id.display_name if order.team_id else "",
            "can_confirm": can_confirm,
            "can_update": order.state in {"draft", "sent"} and self._can_record_write(order),
            "can_send": False,
            "lines": [
                self._serialize_sales_order_line(line)
                for line in order.order_line.sorted(lambda item: (item.sequence, item.id))
                if not line.display_type
            ],
        }

    def _client_sale_orders(self, partner_id):
        partner = self._client_record(partner_id)
        if not partner:
            return self._error(_("Client not found."), status=404)
        SaleOrder = request.env["sale.order"]
        SaleOrder.check_access_rights("read")
        limit, offset = self._limit_offset()
        domain = self._order_domain_for_client(partner)
        orders = SaleOrder.search(domain, order="create_date desc, id desc", limit=limit, offset=offset)
        count = SaleOrder.search_count(domain)
        next_offset = offset + len(orders)
        return self._json(
            {
                "items": [self._serialize_sales_order(order) for order in orders],
                "count": count,
                "limit": limit,
                "offset": offset,
                "next_offset": next_offset if next_offset < count else None,
            }
        )

    def _validated_order_lines(self, payload):
        raw_lines = payload.get("lines") or []
        if not isinstance(raw_lines, list):
            raise ValidationError(_("Order lines payload must be a list."))
        aggregated = OrderedDict()
        for item in raw_lines:
            if not isinstance(item, dict):
                raise ValidationError(_("Each order line must be an object."))
            try:
                product_id = int(item.get("product_id") or 0)
            except Exception:
                product_id = 0
            quantity = self._payload_float(item, "qty")
            if quantity is None:
                quantity = self._payload_float(item, "quantity")
            if product_id <= 0:
                raise ValidationError(_("Each order line requires a product."))
            if quantity is None or quantity <= 0:
                raise ValidationError(
                    _("Each order line quantity must be greater than zero.")
                )
            aggregated[product_id] = (aggregated.get(product_id) or 0.0) + quantity
        if not aggregated:
            raise ValidationError(_("At least one order line is required."))
        return [
            {"product_id": product_id, "qty": quantity}
            for product_id, quantity in aggregated.items()
        ]

    def _validated_products(self, line_values):
        Product = request.env["product.product"]
        Product.check_access_rights("read")
        product_ids = [line["product_id"] for line in line_values]
        products = Product.search(
            [
                ("id", "in", product_ids),
                ("sale_ok", "=", True),
                ("active", "=", True),
            ]
        )
        if len(products) != len(set(product_ids)):
            raise ValidationError(
                _("One or more selected products are not available for sale.")
            )
        product_by_id = {product.id: product for product in products}
        for product in products:
            product_warning = self._product_sale_warning(product)
            if product_warning["is_blocking"]:
                raise ValidationError(
                    product_warning["message"]
                    or _("One or more selected products are blocked for sale.")
                )
        return product_by_id

    def _apply_order_lines(self, order, line_values, replace=False):
        if replace:
            order.order_line.filtered(lambda line: not line.display_type).unlink()
        self._validated_products(line_values)
        for line in line_values:
            order._update_order_line_info(line["product_id"], line["qty"])

    def _sale_order_create_values(self, partner, note):
        order_defaults = self._draft_sale_order(partner)
        values = {
            "partner_id": self._sales_partner_for_client(partner).id,
            "company_id": request.env.company.id,
            "user_id": order_defaults.user_id.id or request.env.user.id,
            "team_id": order_defaults.team_id.id if order_defaults.team_id else False,
            "pricelist_id": order_defaults.pricelist_id.id
            if order_defaults.pricelist_id
            else False,
            "payment_term_id": order_defaults.payment_term_id.id
            if order_defaults.payment_term_id
            else False,
            "partner_invoice_id": order_defaults.partner_invoice_id.id
            if order_defaults.partner_invoice_id
            else False,
            "partner_shipping_id": order_defaults.partner_shipping_id.id
            if order_defaults.partner_shipping_id
            else False,
            "warehouse_id": order_defaults.warehouse_id.id
            if order_defaults.warehouse_id
            else False,
        }
        cleaned_note = (note or "").strip()
        if cleaned_note:
            values["note"] = cleaned_note
        return values

    def _client_sale_order_create(self, partner_id):
        partner = self._client_record(partner_id)
        if not partner:
            return self._error(_("Client not found."), status=404)
        payload = self._json_body()
        partner_warning = self._partner_sale_warning(self._sales_partner_for_client(partner))
        if partner_warning["is_blocking"]:
            return self._error(partner_warning["message"] or _("This customer is blocked for sales."))
        SaleOrder = request.env["sale.order"]
        SaleOrder.check_access_rights("create")
        line_values = self._validated_order_lines(payload)
        order = SaleOrder.with_context(
            default_partner_id=self._sales_partner_for_client(partner).id,
            default_company_id=request.env.company.id,
            default_user_id=request.env.user.id,
        ).create(self._sale_order_create_values(partner, payload.get("note")))
        self._apply_order_lines(order, line_values)
        return self._json(
            {
                "message": _("Sales order created successfully."),
                "order": self._serialize_sales_order(order),
            },
            status=201,
        )

    def _sale_order_record(self, order_id):
        self._ensure_sales_models()
        SaleOrder = request.env["sale.order"]
        SaleOrder.check_access_rights("read")
        return SaleOrder.search([("id", "=", order_id)], limit=1)

    def _sale_order_detail(self, order_id):
        order = self._sale_order_record(order_id)
        if not order:
            return self._error(_("Sales order not found."), status=404)
        return self._json(self._serialize_sales_order(order))

    def _sale_order_update(self, order_id):
        order = self._sale_order_record(order_id)
        if not order:
            return self._error(_("Sales order not found."), status=404)
        if not self._can_record_write(order):
            raise AccessError(_("You do not have permission to update this sales order."))
        if order.state not in {"draft", "sent"}:
            return self._error(_("Only draft quotations can be updated."), status=400)
        payload = self._json_body()
        values = {}
        if "note" in payload:
            values["note"] = (payload.get("note") or "").strip()
        if values:
            order.write(values)
        if "lines" in payload:
            line_values = self._validated_order_lines(payload)
            self._apply_order_lines(order, line_values, replace=True)
        return self._json(
            {
                "message": _("Sales order updated successfully."),
                "order": self._serialize_sales_order(order),
            }
        )

    def _sale_order_confirm(self, order_id):
        order = self._sale_order_record(order_id)
        if not order:
            return self._error(_("Sales order not found."), status=404)
        if not self._can_record_write(order):
            raise AccessError(_("You do not have permission to confirm this sales order."))
        if order.state not in {"draft", "sent"}:
            return self._error(_("Only draft quotations can be confirmed."), status=400)
        order.action_confirm()
        return self._json(
            {
                "message": _("Sales order confirmed successfully."),
                "order": self._serialize_sales_order(order),
            }
        )

    def _serialize_sales_product(self, product, draft_order):
        price = product.lst_price or 0.0
        currency = (
            draft_order.currency_id.name
            if draft_order.currency_id
            else request.env.company.currency_id.name
        )
        if draft_order.pricelist_id and draft_order.currency_id:
            price = draft_order.pricelist_id._get_product_price(
                product=product,
                quantity=1.0,
                currency=draft_order.currency_id,
                date=draft_order.date_order or fields.Date.context_today(request.env.user),
            )
        warning = self._product_sale_warning(product)
        return {
            "id": str(product.id),
            "name": product.display_name or "",
            "default_code": product.default_code or "",
            "barcode": product.barcode or "",
            "uom_name": product.uom_id.name if product.uom_id else "",
            "price": price,
            "currency": currency,
            "warning": warning["message"],
            "is_blocked": warning["is_blocking"],
        }

    def _sales_products(self):
        partner_id = self._arg_int("client_id", 0)
        if partner_id <= 0:
            return self._error(_("client_id is required."))
        partner = self._client_record(partner_id)
        if not partner:
            return self._error(_("Client not found."), status=404)
        Product = request.env["product.product"]
        Product.check_access_rights("read")
        search = (self._arg("search") or "").strip()
        limit, offset = self._limit_offset()
        if not search:
            return self._json(
                {
                    "items": [],
                    "count": 0,
                    "limit": limit,
                    "offset": offset,
                    "next_offset": None,
                }
            )
        domain = expression.AND(
            [
                [
                    ("sale_ok", "=", True),
                    ("active", "=", True),
                ],
                self._domain_for_search(["name", "default_code", "barcode"], search),
            ]
        )
        draft_order = self._draft_sale_order(partner)
        count = Product.search_count(domain)
        products = Product.search(domain, order="default_code, name, id", limit=limit, offset=offset)
        next_offset = offset + len(products)
        return self._json(
            {
                "items": [
                    self._serialize_sales_product(product, draft_order)
                    for product in products
                ],
                "count": count,
                "limit": limit,
                "offset": offset,
                "next_offset": next_offset if next_offset < count else None,
            }
        )
