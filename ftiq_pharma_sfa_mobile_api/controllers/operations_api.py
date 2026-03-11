from datetime import timedelta

from odoo import _, fields, http
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Command
from odoo.http import request
from odoo.osv import expression

from odoo.addons.ftiq_pharma_sfa.controllers.dashboard import FtiqDashboardController

from .base_api import FtiqMobileApiBase


class FtiqMobileOperationsApi(FtiqMobileApiBase):
    @http.route("/ftiq_mobile_api/v1/dashboard", type="http", auth="user", methods=["GET"], csrf=False)
    def dashboard(self, **kwargs):
        return self._dispatch(self._dashboard)

    @http.route("/ftiq_mobile_api/v1/reference-data", type="http", auth="user", methods=["GET"], csrf=False)
    def reference_data(self, **kwargs):
        return self._dispatch(self._reference_data)

    @http.route("/ftiq_mobile_api/v1/catalog/products", type="http", auth="user", methods=["GET"], csrf=False)
    def catalog_products(self, **kwargs):
        return self._dispatch(self._catalog_products)

    @http.route("/ftiq_mobile_api/v1/catalog/materials", type="http", auth="user", methods=["GET"], csrf=False)
    def catalog_materials(self, **kwargs):
        return self._dispatch(self._catalog_materials)

    @http.route("/ftiq_mobile_api/v1/clients", type="http", auth="user", methods=["GET"], csrf=False)
    def clients(self, **kwargs):
        return self._dispatch(self._clients)

    @http.route("/ftiq_mobile_api/v1/clients/<int:partner_id>", type="http", auth="user", methods=["GET"], csrf=False)
    def client_detail(self, partner_id, **kwargs):
        return self._dispatch(lambda: self._client_detail(partner_id))

    @http.route("/ftiq_mobile_api/v1/clients/<int:partner_id>/open-invoices", type="http", auth="user", methods=["GET"], csrf=False)
    def client_open_invoices(self, partner_id, **kwargs):
        return self._dispatch(lambda: self._client_open_invoices(partner_id))

    @http.route("/ftiq_mobile_api/v1/invoices", type="http", auth="user", methods=["GET"], csrf=False)
    def invoices(self, **kwargs):
        return self._dispatch(self._invoices)

    @http.route("/ftiq_mobile_api/v1/invoices/<int:invoice_id>", type="http", auth="user", methods=["GET"], csrf=False)
    def invoice_detail(self, invoice_id, **kwargs):
        return self._dispatch(lambda: self._invoice_detail(invoice_id))

    @http.route("/ftiq_mobile_api/v1/finance/workspace", type="http", auth="user", methods=["GET"], csrf=False)
    def finance_workspace(self, **kwargs):
        return self._dispatch(self._finance_workspace)

    @http.route("/ftiq_mobile_api/v1/notifications", type="http", auth="user", methods=["GET"], csrf=False)
    def notifications(self, **kwargs):
        return self._dispatch(self._notifications)

    @http.route("/ftiq_mobile_api/v1/notifications/read", type="http", auth="user", methods=["POST"], csrf=False)
    def notifications_read(self, **kwargs):
        return self._dispatch(self._notifications_read)

    @http.route("/ftiq_mobile_api/v1/activities", type="http", auth="user", methods=["GET"], csrf=False)
    def activities(self, **kwargs):
        return self._dispatch(self._activities)

    @http.route("/ftiq_mobile_api/v1/activities/<int:activity_id>/done", type="http", auth="user", methods=["POST"], csrf=False)
    def activity_done(self, activity_id, **kwargs):
        return self._dispatch(lambda: self._activity_done(activity_id))

    @http.route("/ftiq_mobile_api/v1/attendance/active", type="http", auth="user", methods=["GET"], csrf=False)
    def active_attendance(self, **kwargs):
        return self._dispatch(self._active_attendance)

    @http.route("/ftiq_mobile_api/v1/attendance/history", type="http", auth="user", methods=["GET"], csrf=False)
    def attendance_history(self, **kwargs):
        return self._dispatch(self._attendance_history)

    @http.route("/ftiq_mobile_api/v1/attendance/check-out", type="http", auth="user", methods=["POST"], csrf=False)
    def attendance_check_out(self, **kwargs):
        return self._dispatch(self._attendance_check_out)

    @http.route("/ftiq_mobile_api/v1/visits", type="http", auth="user", methods=["GET", "POST"], csrf=False)
    def visits(self, **kwargs):
        if request.httprequest.method == "POST":
            return self._dispatch(self._visit_create)
        return self._dispatch(self._visits)

    @http.route("/ftiq_mobile_api/v1/visits/<int:visit_id>", type="http", auth="user", methods=["GET"], csrf=False)
    def visit_detail(self, visit_id, **kwargs):
        return self._dispatch(lambda: self._visit_detail(visit_id))

    @http.route("/ftiq_mobile_api/v1/visits/<int:visit_id>/save", type="http", auth="user", methods=["POST"], csrf=False)
    def visit_save(self, visit_id, **kwargs):
        return self._dispatch(lambda: self._visit_save(visit_id))

    @http.route("/ftiq_mobile_api/v1/visits/<int:visit_id>/start", type="http", auth="user", methods=["POST"], csrf=False)
    def visit_start(self, visit_id, **kwargs):
        return self._dispatch(lambda: self._visit_action(visit_id, "action_start"))

    @http.route("/ftiq_mobile_api/v1/visits/<int:visit_id>/end", type="http", auth="user", methods=["POST"], csrf=False)
    def visit_end(self, visit_id, **kwargs):
        return self._dispatch(lambda: self._visit_action(visit_id, "action_end"))

    @http.route("/ftiq_mobile_api/v1/visits/<int:visit_id>/submit", type="http", auth="user", methods=["POST"], csrf=False)
    def visit_submit(self, visit_id, **kwargs):
        return self._dispatch(lambda: self._visit_action(visit_id, "action_submit"))

    @http.route("/ftiq_mobile_api/v1/visits/<int:visit_id>/approve", type="http", auth="user", methods=["POST"], csrf=False)
    def visit_approve(self, visit_id, **kwargs):
        return self._dispatch(lambda: self._visit_action(visit_id, "action_approve"))

    @http.route("/ftiq_mobile_api/v1/visits/<int:visit_id>/return", type="http", auth="user", methods=["POST"], csrf=False)
    def visit_return(self, visit_id, **kwargs):
        return self._dispatch(lambda: self._visit_action(visit_id, "action_return"))

    @http.route("/ftiq_mobile_api/v1/plans", type="http", auth="user", methods=["GET"], csrf=False)
    def plans(self, **kwargs):
        return self._dispatch(self._plans)

    @http.route("/ftiq_mobile_api/v1/plans/<int:plan_id>", type="http", auth="user", methods=["GET"], csrf=False)
    def plan_detail(self, plan_id, **kwargs):
        return self._dispatch(lambda: self._plan_detail(plan_id))

    @http.route("/ftiq_mobile_api/v1/tasks", type="http", auth="user", methods=["GET"], csrf=False)
    def tasks(self, **kwargs):
        return self._dispatch(self._tasks)

    @http.route("/ftiq_mobile_api/v1/tasks/<int:task_id>", type="http", auth="user", methods=["GET"], csrf=False)
    def task_detail(self, task_id, **kwargs):
        return self._dispatch(lambda: self._task_detail(task_id))

    @http.route("/ftiq_mobile_api/v1/tasks/<int:task_id>/save", type="http", auth="user", methods=["POST"], csrf=False)
    def task_save(self, task_id, **kwargs):
        return self._dispatch(lambda: self._task_save(task_id))

    @http.route("/ftiq_mobile_api/v1/tasks/<int:task_id>/start", type="http", auth="user", methods=["POST"], csrf=False)
    def task_start(self, task_id, **kwargs):
        return self._dispatch(lambda: self._task_action(task_id, "action_start"))

    @http.route("/ftiq_mobile_api/v1/tasks/<int:task_id>/complete", type="http", auth="user", methods=["POST"], csrf=False)
    def task_complete(self, task_id, **kwargs):
        return self._dispatch(lambda: self._task_action(task_id, "action_complete"))

    @http.route("/ftiq_mobile_api/v1/tasks/<int:task_id>/submit", type="http", auth="user", methods=["POST"], csrf=False)
    def task_submit(self, task_id, **kwargs):
        return self._dispatch(lambda: self._task_action(task_id, "action_submit"))

    @http.route("/ftiq_mobile_api/v1/tasks/<int:task_id>/confirm", type="http", auth="user", methods=["POST"], csrf=False)
    def task_confirm(self, task_id, **kwargs):
        return self._dispatch(lambda: self._task_action(task_id, "action_confirm"))

    @http.route("/ftiq_mobile_api/v1/tasks/<int:task_id>/return", type="http", auth="user", methods=["POST"], csrf=False)
    def task_return(self, task_id, **kwargs):
        return self._dispatch(lambda: self._task_action(task_id, "action_return"))

    @http.route("/ftiq_mobile_api/v1/expenses", type="http", auth="user", methods=["GET", "POST"], csrf=False)
    def expenses(self, **kwargs):
        if request.httprequest.method == "POST":
            return self._dispatch(self._expense_create)
        return self._dispatch(self._expenses)

    @http.route("/ftiq_mobile_api/v1/expenses/<int:expense_id>", type="http", auth="user", methods=["GET"], csrf=False)
    def expense_detail(self, expense_id, **kwargs):
        return self._dispatch(lambda: self._expense_detail(expense_id))

    @http.route("/ftiq_mobile_api/v1/expenses/<int:expense_id>/save", type="http", auth="user", methods=["POST"], csrf=False)
    def expense_save(self, expense_id, **kwargs):
        return self._dispatch(lambda: self._expense_save(expense_id))

    @http.route("/ftiq_mobile_api/v1/expenses/<int:expense_id>/submit", type="http", auth="user", methods=["POST"], csrf=False)
    def expense_submit(self, expense_id, **kwargs):
        return self._dispatch(lambda: self._expense_action(expense_id, "action_submit_expenses"))

    @http.route("/ftiq_mobile_api/v1/orders", type="http", auth="user", methods=["GET", "POST"], csrf=False)
    def orders(self, **kwargs):
        if request.httprequest.method == "POST":
            return self._dispatch(self._order_create)
        return self._dispatch(self._orders)

    @http.route("/ftiq_mobile_api/v1/orders/<int:order_id>", type="http", auth="user", methods=["GET"], csrf=False)
    def order_detail(self, order_id, **kwargs):
        return self._dispatch(lambda: self._order_detail(order_id))

    @http.route("/ftiq_mobile_api/v1/orders/<int:order_id>/save", type="http", auth="user", methods=["POST"], csrf=False)
    def order_save(self, order_id, **kwargs):
        return self._dispatch(lambda: self._order_save(order_id))

    @http.route("/ftiq_mobile_api/v1/orders/<int:order_id>/confirm", type="http", auth="user", methods=["POST"], csrf=False)
    def order_confirm(self, order_id, **kwargs):
        return self._dispatch(lambda: self._order_confirm(order_id))

    @http.route("/ftiq_mobile_api/v1/collections", type="http", auth="user", methods=["GET", "POST"], csrf=False)
    def collections(self, **kwargs):
        if request.httprequest.method == "POST":
            return self._dispatch(self._collection_create)
        return self._dispatch(self._collections)

    @http.route("/ftiq_mobile_api/v1/collections/<int:payment_id>", type="http", auth="user", methods=["GET"], csrf=False)
    def collection_detail(self, payment_id, **kwargs):
        return self._dispatch(lambda: self._collection_detail(payment_id))

    @http.route("/ftiq_mobile_api/v1/collections/<int:payment_id>/save", type="http", auth="user", methods=["POST"], csrf=False)
    def collection_save(self, payment_id, **kwargs):
        return self._dispatch(lambda: self._collection_save(payment_id))

    @http.route("/ftiq_mobile_api/v1/collections/<int:payment_id>/collect", type="http", auth="user", methods=["POST"], csrf=False)
    def collection_collect(self, payment_id, **kwargs):
        return self._dispatch(lambda: self._collection_action(payment_id, "action_ftiq_collect"))

    @http.route("/ftiq_mobile_api/v1/collections/<int:payment_id>/deposit", type="http", auth="user", methods=["POST"], csrf=False)
    def collection_deposit(self, payment_id, **kwargs):
        return self._dispatch(lambda: self._collection_action(payment_id, "action_ftiq_deposit"))

    @http.route("/ftiq_mobile_api/v1/collections/<int:payment_id>/verify", type="http", auth="user", methods=["POST"], csrf=False)
    def collection_verify(self, payment_id, **kwargs):
        return self._dispatch(lambda: self._collection_action(payment_id, "action_ftiq_verify"))

    @http.route("/ftiq_mobile_api/v1/stock-checks", type="http", auth="user", methods=["GET", "POST"], csrf=False)
    def stock_checks(self, **kwargs):
        if request.httprequest.method == "POST":
            return self._dispatch(self._stock_check_create)
        return self._dispatch(self._stock_checks)

    @http.route("/ftiq_mobile_api/v1/stock-checks/<int:check_id>", type="http", auth="user", methods=["GET"], csrf=False)
    def stock_check_detail(self, check_id, **kwargs):
        return self._dispatch(lambda: self._stock_check_detail(check_id))

    @http.route("/ftiq_mobile_api/v1/stock-checks/<int:check_id>/save", type="http", auth="user", methods=["POST"], csrf=False)
    def stock_check_save(self, check_id, **kwargs):
        return self._dispatch(lambda: self._stock_check_save(check_id))

    @http.route("/ftiq_mobile_api/v1/stock-checks/<int:check_id>/submit", type="http", auth="user", methods=["POST"], csrf=False)
    def stock_check_submit(self, check_id, **kwargs):
        return self._dispatch(lambda: self._stock_check_action(check_id, "action_submit"))

    @http.route("/ftiq_mobile_api/v1/stock-checks/<int:check_id>/review", type="http", auth="user", methods=["POST"], csrf=False)
    def stock_check_review(self, check_id, **kwargs):
        return self._dispatch(lambda: self._stock_check_action(check_id, "action_review"))

    @http.route("/ftiq_mobile_api/v1/stock-checks/<int:check_id>/reset", type="http", auth="user", methods=["POST"], csrf=False)
    def stock_check_reset(self, check_id, **kwargs):
        return self._dispatch(lambda: self._stock_check_action(check_id, "action_reset_draft"))

    def _dashboard(self):
        return self._ok(FtiqDashboardController().get_dashboard_data())

    def _reference_data(self):
        user = self._current_user()
        journals = request.env["account.journal"].search([
            ("company_id", "=", user.company_id.id),
            ("type", "in", ("bank", "cash")),
            ("active", "=", True),
        ], order="sequence, id")
        call_reasons = request.env["ftiq.call.reason"].search([], order="name")
        expense_products = request.env["product.product"].search([
            ("can_be_expensed", "=", True),
            ("active", "=", True),
        ], order="name", limit=100)
        expense_type_field = request.env["hr.expense"]._fields["ftiq_expense_type"]
        visit_field = request.env["ftiq.visit"]._fields["outcome"]
        return self._ok({
            "role": self._role_of(user),
            "company": self._serialize_company(user.company_id),
            "call_reasons": [self._serialize_call_reason(reason) for reason in call_reasons],
            "visit_outcomes": [{"value": value, "label": label} for value, label in visit_field.selection],
            "payment_journals": [self._serialize_payment_journal(journal) for journal in journals],
            "expense_types": [{"value": value, "label": label} for value, label in expense_type_field.selection],
            "expense_products": [self._serialize_product(product) for product in expense_products],
        })

    def _catalog_products(self):
        query = request.httprequest.args.get("query", "")
        limit = self._args_int("limit", 25)
        domain = [("sale_ok", "=", True), ("active", "=", True)]
        if query:
            domain.extend([
                "|",
                "|",
                ("name", "ilike", query),
                ("default_code", "ilike", query),
                ("barcode", "ilike", query),
            ])
        products = request.env["product.product"].search(domain, order="name", limit=limit)
        items = [self._serialize_product(product) for product in products]
        return self._ok({"items": items}, meta={"count": len(items)})

    def _catalog_materials(self):
        product_id = self._args_int("product_id", 0)
        limit = self._args_int("limit", 50)
        domain = [("active", "=", True)]
        if product_id:
            domain.extend([
                "|",
                ("product_id", "=", product_id),
                ("material_scope", "in", ("visit", "both")),
            ])
        materials = request.env["ftiq.marketing.material"].search(domain, order="sequence, id", limit=limit)
        items = [self._serialize_material(material) for material in materials]
        return self._ok({"items": items}, meta={"count": len(items)})

    def _clients(self):
        service = request.env["ftiq.client.search.service"]
        limit = self._args_int("limit", 25)
        query = request.httprequest.args.get("query", "")
        client_code = request.httprequest.args.get("client_code", "")
        city_id = self._args_int("city_id", 0)
        area_id = self._args_int("area_id", 0)
        latitude = self._args_float("latitude", 0.0)
        longitude = self._args_float("longitude", 0.0)
        radius_km = self._args_float("radius_km", 0.0)
        items = service.search_clients(
            search_term=query,
            client_code=client_code,
            city_id=city_id or False,
            area_id=area_id or False,
            latitude=latitude or False,
            longitude=longitude or False,
            radius_km=radius_km,
            limit=limit,
        )
        return self._ok({"items": items}, meta={"count": len(items)})

    def _client_detail(self, partner_id):
        service = request.env["ftiq.client.search.service"]
        latitude = self._args_float("latitude", 0.0)
        longitude = self._args_float("longitude", 0.0)
        card = service.get_client_card(
            partner_id,
            latitude=latitude or False,
            longitude=longitude or False,
        )
        if not card:
            return self._error(_("Client not found."), status=404, code="not_found")
        return self._ok(card)

    def _client_open_invoices(self, partner_id):
        partner = self._browse_mobile_client(partner_id)
        if not partner:
            return self._error(_("Client not found."), status=404, code="not_found")
        invoices = self._get_open_invoices_for_partner(partner)
        items = [self._serialize_invoice(invoice) for invoice in invoices]
        return self._ok({"items": items}, meta={"count": len(items)})

    def _invoices(self):
        limit = self._args_int("limit", 40)
        partner_id = self._args_int("partner_id", 0)
        payment_state = request.httprequest.args.get("payment_state")
        domain = [("amount_residual", ">", 0)]
        if partner_id:
            domain.append(("partner_id", "=", partner_id))
        if payment_state:
            domain.append(("payment_state", "=", payment_state))
        invoices = self._search_scoped(
            "account.move",
            domain,
            order="invoice_date_due asc, invoice_date asc, id desc",
            limit=limit,
        )
        items = [self._serialize_invoice(invoice) for invoice in invoices]
        return self._ok({"items": items}, meta={"count": len(items)})

    def _invoice_detail(self, invoice_id):
        invoice = self._browse_scoped("account.move", invoice_id).exists()
        if not invoice:
            return self._error(_("Invoice not found."), status=404, code="not_found")
        return self._ok(self._serialize_invoice(invoice, detailed=True))

    def _finance_workspace(self):
        self._sync_live_activity_notifications()
        user = self._current_user()
        role = self._current_role()
        invoice_limit = self._args_int("invoice_limit", 8)
        collection_limit = self._args_int("collection_limit", 8)
        schedule_limit = self._args_int("schedule_limit", 8)
        notification_limit = self._args_int("notification_limit", 8)

        open_invoice_domain = [("amount_residual", ">", 0)]
        collection_schedule_domain = [
            ("state", "not in", ("completed", "confirmed", "cancelled")),
            "|",
            ("task_type", "=", "collection"),
            ("payment_id", "!=", False),
        ]
        pending_collection_domain = [("ftiq_collection_state", "in", ("draft", "collected", "deposited"))]
        finance_notification_domain = [("category", "in", ("collection", "invoice", "finance", "system"))]
        unread_finance_notification_domain = expression.AND([
            finance_notification_domain,
            [("is_read", "=", False)],
        ])
        overdue_schedule_domain = expression.AND([
            collection_schedule_domain,
            [("scheduled_date", "<", fields.Datetime.now())],
        ])

        open_invoices = self._search_scoped(
            "account.move",
            open_invoice_domain,
            order="invoice_date_due asc, invoice_date asc, id desc",
            limit=invoice_limit,
        )
        all_open_invoices = self._search_scoped("account.move", open_invoice_domain)

        collections = self._search_scoped(
            "account.payment",
            order="date desc, id desc",
            limit=collection_limit,
        )
        all_collections = self._search_scoped("account.payment")

        try:
            schedules = self._search_scoped(
                "ftiq.daily.task",
                collection_schedule_domain,
                order="scheduled_date asc, priority desc, id desc",
                limit=schedule_limit,
            )
            schedule_count = self._search_scoped(
                "ftiq.daily.task",
                collection_schedule_domain,
            ).__len__()
            overdue_schedule_count = self._search_scoped(
                "ftiq.daily.task",
                overdue_schedule_domain,
            ).__len__()
        except AccessError:
            schedules = request.env["ftiq.daily.task"]
            schedule_count = 0
            overdue_schedule_count = 0
        notifications = self._search_scoped(
            "ftiq.mobile.notification",
            finance_notification_domain,
            order="create_date desc, id desc",
            limit=notification_limit,
        )

        data = {
            "role": role,
            "can_publish_notifications": role in {"supervisor", "manager"},
            "currency_symbol": user.company_id.currency_id.symbol or "",
            "generated_at": fields.Datetime.to_string(fields.Datetime.now()),
            "summary": {
                "open_invoice_count": len(all_open_invoices),
                "open_invoice_amount": sum(all_open_invoices.mapped("amount_residual")),
                "collection_count": len(all_collections),
                "collection_amount": sum(all_collections.mapped("amount")),
                "pending_collection_count": self._search_scoped(
                    "account.payment",
                    pending_collection_domain,
                ).__len__(),
                "schedule_count": schedule_count,
                "overdue_schedule_count": overdue_schedule_count,
                "notification_count": self._search_scoped(
                    "ftiq.mobile.notification",
                    finance_notification_domain,
                ).__len__(),
                "alert_count": self._search_scoped(
                    "ftiq.mobile.notification",
                    unread_finance_notification_domain,
                ).__len__(),
            },
            "collections": [self._serialize_collection(payment) for payment in collections],
            "invoices": [self._serialize_invoice(invoice) for invoice in open_invoices],
            "schedules": [self._serialize_task(task) for task in schedules],
            "notifications": [self._serialize_mobile_notification(notification) for notification in notifications],
        }
        return self._ok(data)

    def _notifications(self):
        self._sync_live_activity_notifications()
        limit = self._args_int("limit", 40)
        unread_only = self._args_bool("unread_only", False)
        category = (request.httprequest.args.get("category") or "").strip()
        domain = []
        if unread_only:
            domain.append(("is_read", "=", False))
        if category:
            domain.append(("category", "=", category))
        notifications = self._search_scoped(
            "ftiq.mobile.notification",
            domain,
            order="create_date desc, id desc",
            limit=limit,
        )
        items = [self._serialize_mobile_notification(notification) for notification in notifications]
        return self._ok(
            {
                "items": items,
                "count": len(items),
                "unread_count": self._search_scoped(
                    "ftiq.mobile.notification",
                    expression.AND([domain, [("is_read", "=", False)]]) if domain else [("is_read", "=", False)],
                ).__len__(),
            }
        )

    def _notifications_read(self):
        payload = self._json_body()
        mark_all = self._payload_bool(payload, "mark_all", False)
        ids = [
            int(item)
            for item in (payload.get("ids") or [])
            if str(item).strip().isdigit()
        ]
        if mark_all:
            notifications = self._search_scoped(
                "ftiq.mobile.notification",
                [("is_read", "=", False)],
            )
        else:
            notifications = self._search_scoped(
                "ftiq.mobile.notification",
                [("id", "in", ids)] if ids else [("id", "=", 0)],
            )
        notifications.action_mark_read()
        return self._ok(
            {
                "updated": len(notifications),
                "summary": self._notification_summary(),
            }
        )

    def _activities(self):
        limit = self._args_int("limit", 40)
        state = (request.httprequest.args.get("state") or "").strip()
        model_name = (request.httprequest.args.get("model") or "").strip()
        domain = []
        if state:
            domain.append(("state", "=", state))
        if model_name:
            domain.append(("res_model", "=", model_name))
        activities = self._search_scoped(
            "mail.activity",
            domain,
            order="date_deadline asc, id asc",
            limit=limit,
        )
        items = [self._serialize_activity(activity) for activity in activities]
        return self._ok({"items": items}, meta={"count": len(items)})

    def _activity_done(self, activity_id):
        payload = self._json_body()
        activity = self._browse_scoped("mail.activity", activity_id).exists()
        if not activity:
            return self._error(_("Activity not found."), status=404, code="not_found")
        feedback = (payload.get("feedback") or "").strip()
        if feedback:
            activity.action_feedback(feedback=feedback)
        else:
            activity.action_done()
        return self._ok(
            {
                "activity_id": activity_id,
                "summary": self._notification_summary(),
            }
        )

    def _active_attendance(self):
        user = self._current_user()
        attendance = request.env["ftiq.field.attendance"].get_active_attendance(
            user.id,
            fields.Date.context_today(user),
        )
        return self._ok(self._serialize_attendance(attendance))

    def _attendance_history(self):
        limit = self._args_int("limit", 20)
        attendances = self._search_scoped(
            "ftiq.field.attendance",
            order="date desc, check_in_time desc, id desc",
            limit=limit,
        )
        items = [self._serialize_attendance(attendance) for attendance in attendances]
        return self._ok({"items": items}, meta={"count": len(items)})

    def _attendance_check_out(self):
        payload = self._json_body()
        replay = self._replay_mobile_request(
            payload,
            lambda record, detailed=True: self._serialize_attendance(record),
            detailed=False,
        )
        if replay:
            return replay
        user = self._current_user()
        attendance = request.env["ftiq.field.attendance"].get_active_attendance(
            user.id,
            fields.Date.context_today(user),
        )
        if not attendance:
            return self._error(_("No active attendance found."), status=404, code="not_found")
        attendance.with_context(**self._geo_context_from_payload(payload)).action_check_out()
        self._remember_mobile_request(payload, attendance)
        return self._ok(self._serialize_attendance(attendance))

    def _visits(self):
        limit = self._args_int("limit", 20)
        state = request.httprequest.args.get("state")
        partner_id = self._args_int("partner_id", 0)
        domain = []
        if state:
            domain.append(("state", "=", state))
        if partner_id:
            domain.append(("partner_id", "=", partner_id))
        visits = self._search_scoped(
            "ftiq.visit",
            domain,
            order="visit_date desc, id desc",
            limit=limit,
        )
        items = [self._serialize_visit(visit) for visit in visits]
        return self._ok({"items": items}, meta={"count": len(items)})

    def _visit_detail(self, visit_id):
        visit = self._browse_scoped("ftiq.visit", visit_id).exists()
        if not visit:
            return self._error(_("Visit not found."), status=404, code="not_found")
        return self._ok(self._serialize_visit(visit, detailed=True))

    def _visit_create(self):
        payload = self._json_body()
        replay = self._replay_mobile_request(
            payload,
            lambda record, detailed=True: self._serialize_visit(record, detailed=detailed),
        )
        if replay:
            return replay
        plan_line = self._resolve_plan_line_from_payload(payload)
        if payload.get("plan_line_id") and not plan_line:
            return self._error(_("Plan line not found."), status=404, code="not_found")
        if plan_line:
            self._ensure_current_user_owns(plan_line, "create this visit")
        partner_id = payload.get("partner_id")
        if plan_line and not partner_id:
            partner_id = plan_line.partner_id.id
        if plan_line and partner_id and plan_line.partner_id and partner_id != plan_line.partner_id.id:
            return self._error(_("The selected plan line belongs to another client."), code="invalid_source")
        if not partner_id:
            return self._error(_("partner_id is required."))
        values = {
            "partner_id": partner_id,
            "user_id": self._current_user().id,
            "visit_date": payload.get("visit_date") or str(fields.Date.context_today(self._current_user())),
            "plan_line_id": plan_line.id if plan_line else False,
            "unplanned_reason": payload.get("unplanned_reason") or "",
            "general_feedback": payload.get("general_feedback") or "",
            "outcome": payload.get("outcome") or False,
        }
        visit = request.env["ftiq.visit"].create(values)
        if "product_lines" in payload or "material_logs" in payload:
            self._save_visit_payload(visit, payload)
        self._remember_mobile_request(payload, visit)
        return self._ok(self._serialize_visit(visit, detailed=True), status=201)

    def _visit_save(self, visit_id):
        payload = self._json_body()
        replay = self._replay_mobile_request(
            payload,
            lambda record, detailed=True: self._serialize_visit(record, detailed=detailed),
        )
        if replay:
            return replay
        visit = self._browse_scoped("ftiq.visit", visit_id).exists()
        if not visit:
            return self._error(_("Visit not found."), status=404, code="not_found")
        self._ensure_current_user_owns(visit, "update this visit")
        self._save_visit_payload(visit, payload)
        self._remember_mobile_request(payload, visit)
        return self._ok(self._serialize_visit(visit, detailed=True))

    def _visit_action(self, visit_id, method_name):
        payload = self._json_body()
        replay = self._replay_mobile_request(
            payload,
            lambda record, detailed=True: self._serialize_visit(record, detailed=detailed),
        )
        if replay:
            return replay
        visit = self._browse_scoped("ftiq.visit", visit_id).exists()
        if not visit:
            return self._error(_("Visit not found."), status=404, code="not_found")
        if method_name in {"action_approve", "action_return"}:
            self._ensure_role({"supervisor", "manager"}, "review this visit")
        else:
            self._ensure_current_user_owns(visit, "change this visit")
        getattr(visit.with_context(**self._geo_context_from_payload(payload)), method_name)()
        self._remember_mobile_request(payload, visit)
        return self._ok(self._serialize_visit(visit, detailed=True))

    def _plans(self):
        limit = self._args_int("limit", 20)
        state = request.httprequest.args.get("state")
        domain = []
        if state:
            domain.append(("state", "=", state))
        plans = self._search_scoped(
            "ftiq.weekly.plan",
            domain,
            order="week_start desc, id desc",
            limit=limit,
        )
        items = [self._serialize_plan(plan) for plan in plans]
        return self._ok({"items": items}, meta={"count": len(items)})

    def _plan_detail(self, plan_id):
        plan = self._browse_scoped("ftiq.weekly.plan", plan_id).exists()
        if not plan:
            return self._error(_("Plan not found."), status=404, code="not_found")
        return self._ok(self._serialize_plan(plan, detailed=True))

    def _tasks(self):
        limit = self._args_int("limit", 20)
        state = request.httprequest.args.get("state")
        domain = []
        if state:
            domain.append(("state", "=", state))
        tasks = self._search_scoped(
            "ftiq.daily.task",
            domain,
            order="scheduled_date asc, priority desc, id desc",
            limit=limit,
        )
        items = [self._serialize_task(task) for task in tasks]
        return self._ok({"items": items}, meta={"count": len(items)})

    def _task_detail(self, task_id):
        task = self._browse_scoped("ftiq.daily.task", task_id).exists()
        if not task:
            return self._error(_("Task not found."), status=404, code="not_found")
        return self._ok(self._serialize_task(task, detailed=True))

    def _task_save(self, task_id):
        payload = self._json_body()
        replay = self._replay_mobile_request(
            payload,
            lambda record, detailed=True: self._serialize_task(record),
            detailed=False,
        )
        if replay:
            return replay
        task = self._browse_scoped("ftiq.daily.task", task_id).exists()
        if not task:
            return self._error(_("Task not found."), status=404, code="not_found")
        self._ensure_current_user_owns(task, "update this task")
        if task.state in {"completed", "confirmed", "cancelled", "submitted"}:
            return self._error(_("This task can no longer be edited."), code="invalid_state")
        values = {}
        for field_name in ("description", "outcome"):
            if field_name in payload:
                values[field_name] = payload.get(field_name) or ""
        for field_name in ("photo_1", "photo_2", "photo_3"):
            if field_name in payload:
                values[field_name] = payload.get(field_name) or False
        if "latitude" in payload:
            values["latitude"] = payload.get("latitude") or 0.0
        if "longitude" in payload:
            values["longitude"] = payload.get("longitude") or 0.0
        if values:
            task.write(values)
        self._remember_mobile_request(payload, task)
        return self._ok(self._serialize_task(task, detailed=True))

    def _task_action(self, task_id, method_name):
        payload = self._json_body()
        replay = self._replay_mobile_request(
            payload,
            lambda record, detailed=True: self._serialize_task(record),
            detailed=False,
        )
        if replay:
            return replay
        task = self._browse_scoped("ftiq.daily.task", task_id).exists()
        if not task:
            return self._error(_("Task not found."), status=404, code="not_found")
        if method_name in {"action_confirm", "action_return"}:
            self._ensure_role({"supervisor", "manager"}, "review this task")
        else:
            self._ensure_current_user_owns(task, "change this task")
        getattr(task.with_context(**self._geo_context_from_payload(payload)), method_name)()
        self._remember_mobile_request(payload, task)
        return self._ok(self._serialize_task(task, detailed=True))

    def _expenses(self):
        limit = self._args_int("limit", 20)
        state = request.httprequest.args.get("state")
        partner_id = self._args_int("partner_id", 0)
        visit_id = self._args_int("visit_id", 0)
        task_id = self._args_int("task_id", 0)
        domain = []
        if state:
            domain.append(("state", "=", state))
        if partner_id:
            domain.append(("ftiq_partner_id", "=", partner_id))
        if visit_id:
            domain.append(("ftiq_visit_id", "=", visit_id))
        if task_id:
            domain.append(("ftiq_daily_task_id", "=", task_id))
        expenses = self._search_scoped(
            "hr.expense",
            domain,
            order="date desc, id desc",
            limit=limit,
        )
        items = [self._serialize_expense(expense) for expense in expenses]
        return self._ok({"items": items}, meta={"count": len(items)})

    def _expense_detail(self, expense_id):
        expense = self._browse_scoped("hr.expense", expense_id).exists()
        if not expense:
            return self._error(_("Expense not found."), status=404, code="not_found")
        return self._ok(self._serialize_expense(expense, detailed=True))

    def _expense_create(self):
        payload = self._json_body()
        replay = self._replay_mobile_request(
            payload,
            lambda record, detailed=True: self._serialize_expense(record, detailed=detailed),
        )
        if replay:
            return replay
        product_id = payload.get("product_id")
        total_amount_currency = payload.get("total_amount_currency")
        if not product_id:
            return self._error(_("product_id is required."))
        if total_amount_currency in (None, "", 0):
            return self._error(_("total_amount_currency is required."))
        visit = self._resolve_visit_from_payload(payload)
        if payload.get("visit_id") and not visit:
            return self._error(_("Visit not found."), status=404, code="not_found")
        task = False
        task_id = payload.get("task_id")
        if task_id:
            task = self._browse_scoped("ftiq.daily.task", task_id).exists()
            if not task:
                return self._error(_("Task not found."), status=404, code="not_found")
        user = self._current_user()
        attendance = False
        attendance_id = payload.get("attendance_id")
        if attendance_id:
            attendance = self._browse_scoped("ftiq.field.attendance", attendance_id).exists()
            if not attendance:
                return self._error(_("Attendance not found."), status=404, code="not_found")
        for source_record in (visit, task, attendance):
            if source_record:
                self._ensure_current_user_owns(source_record, "create this expense")
        if not attendance:
            attendance = request.env["ftiq.field.attendance"].get_active_attendance(
                user.id,
                payload.get("date") or fields.Date.context_today(user),
            )
        if not any((attendance, visit, task)):
            return self._error(
                _("Field expense must be linked to active attendance, a visit, or a task."),
                code="missing_source",
            )
        values = {
            "product_id": product_id,
            "quantity": payload.get("quantity") or 1.0,
            "total_amount_currency": total_amount_currency,
            "description": payload.get("description") or "",
            "date": payload.get("date") or str(fields.Date.context_today(user)),
            "payment_mode": payload.get("payment_mode") or "own_account",
            "is_field_expense": True,
            "ftiq_expense_type": payload.get("expense_type") or False,
            "ftiq_visit_id": visit.id if visit else False,
            "ftiq_daily_task_id": task.id if task else False,
            "ftiq_attendance_id": attendance.id if attendance else False,
            "ftiq_partner_id": payload.get("partner_id")
            or (visit.partner_id.id if visit else False)
            or (task.partner_id.id if task and task.partner_id else False),
            "ftiq_user_id": user.id,
            "ftiq_latitude": payload.get("latitude") or 0.0,
            "ftiq_longitude": payload.get("longitude") or 0.0,
            "ftiq_receipt_image": payload.get("receipt_image") or False,
            "ftiq_receipt_image_name": payload.get("receipt_image_name") or "",
        }
        expense = request.env["hr.expense"].create(values)
        self._remember_mobile_request(payload, expense)
        return self._ok(self._serialize_expense(expense, detailed=True), status=201)

    def _expense_save(self, expense_id):
        payload = self._json_body()
        replay = self._replay_mobile_request(
            payload,
            lambda record, detailed=True: self._serialize_expense(record, detailed=detailed),
        )
        if replay:
            return replay
        expense = self._browse_scoped("hr.expense", expense_id).exists()
        if not expense:
            return self._error(_("Expense not found."), status=404, code="not_found")
        self._ensure_current_user_owns(expense, "update this expense")
        if not expense.is_editable or expense.state not in {"draft", "reported"}:
            return self._error(_("Only editable draft expenses can be changed."), code="invalid_state")
        values = {}
        if "product_id" in payload:
            values["product_id"] = payload.get("product_id") or False
        if "quantity" in payload:
            values["quantity"] = payload.get("quantity") or 1.0
        if "total_amount_currency" in payload:
            values["total_amount_currency"] = payload.get("total_amount_currency") or 0.0
        if "description" in payload:
            values["description"] = payload.get("description") or ""
        if "date" in payload:
            values["date"] = payload.get("date") or str(fields.Date.context_today(self._current_user()))
        if "payment_mode" in payload:
            values["payment_mode"] = payload.get("payment_mode") or "own_account"
        if "expense_type" in payload:
            values["ftiq_expense_type"] = payload.get("expense_type") or False
        if "latitude" in payload:
            values["ftiq_latitude"] = payload.get("latitude") or 0.0
        if "longitude" in payload:
            values["ftiq_longitude"] = payload.get("longitude") or 0.0
        if "receipt_image" in payload:
            values["ftiq_receipt_image"] = payload.get("receipt_image") or False
        if "receipt_image_name" in payload:
            values["ftiq_receipt_image_name"] = payload.get("receipt_image_name") or ""
        if values:
            expense.write(values)
        self._remember_mobile_request(payload, expense)
        return self._ok(self._serialize_expense(expense, detailed=True))

    def _expense_action(self, expense_id, method_name):
        payload = self._json_body()
        replay = self._replay_mobile_request(
            payload,
            lambda record, detailed=True: self._serialize_expense(record, detailed=detailed),
        )
        if replay:
            return replay
        expense = self._browse_scoped("hr.expense", expense_id).exists()
        if not expense:
            return self._error(_("Expense not found."), status=404, code="not_found")
        self._ensure_current_user_owns(expense, "submit this expense")
        getattr(expense, method_name)()
        self._remember_mobile_request(payload, expense)
        return self._ok(self._serialize_expense(expense, detailed=True))

    def _orders(self):
        limit = self._args_int("limit", 20)
        state = request.httprequest.args.get("state")
        partner_id = self._args_int("partner_id", 0)
        visit_id = self._args_int("visit_id", 0)
        domain = []
        if state:
            domain.append(("state", "=", state))
        if partner_id:
            domain.append(("partner_id", "=", partner_id))
        if visit_id:
            domain.append(("ftiq_visit_id", "=", visit_id))
        orders = self._search_scoped(
            "sale.order",
            domain,
            order="date_order desc, id desc",
            limit=limit,
        )
        items = [self._serialize_order(order) for order in orders]
        return self._ok({"items": items}, meta={"count": len(items)})

    def _order_detail(self, order_id):
        order = self._browse_scoped("sale.order", order_id).exists()
        if not order:
            return self._error(_("Order not found."), status=404, code="not_found")
        return self._ok(self._serialize_order(order, detailed=True))

    def _order_create(self):
        payload = self._json_body()
        replay = self._replay_mobile_request(
            payload,
            lambda record, detailed=True: self._serialize_order(record, detailed=detailed),
        )
        if replay:
            return replay
        visit = self._resolve_visit_from_payload(payload)
        if payload.get("visit_id") and not visit:
            return self._error(_("Visit not found."), status=404, code="not_found")
        if visit:
            self._ensure_current_user_owns(visit, "create this order")
        partner_id = payload.get("partner_id") or (visit.partner_id.id if visit else False)
        if not partner_id:
            return self._error(_("partner_id is required."))
        values = {
            "partner_id": partner_id,
            "user_id": self._current_user().id,
            "is_field_order": True,
            "ftiq_visit_id": visit.id if visit else False,
            "ftiq_attendance_id": visit.attendance_id.id if visit and visit.attendance_id else False,
            "ftiq_daily_task_id": visit.plan_line_id.daily_task_id.id if visit and visit.plan_line_id.daily_task_id else False,
            "ftiq_priority": payload.get("priority") or "0",
            "ftiq_delivery_notes": payload.get("delivery_notes") or "",
            "ftiq_latitude": payload.get("latitude") or (visit.start_latitude if visit else 0.0),
            "ftiq_longitude": payload.get("longitude") or (visit.start_longitude if visit else 0.0),
            "order_line": self._prepare_order_line_commands(payload.get("lines") or []),
        }
        order = request.env["sale.order"].create(values)
        self._remember_mobile_request(payload, order)
        return self._ok(self._serialize_order(order, detailed=True), status=201)

    def _order_save(self, order_id):
        payload = self._json_body()
        replay = self._replay_mobile_request(
            payload,
            lambda record, detailed=True: self._serialize_order(record, detailed=detailed),
        )
        if replay:
            return replay
        order = self._browse_scoped("sale.order", order_id).exists()
        if not order:
            return self._error(_("Order not found."), status=404, code="not_found")
        self._ensure_current_user_owns(order, "update this order")
        if order.state not in {"draft", "sent"}:
            return self._error(_("Only draft orders can be edited."), code="invalid_state")
        values = {}
        if "priority" in payload:
            values["ftiq_priority"] = payload.get("priority") or "0"
        if "delivery_notes" in payload:
            values["ftiq_delivery_notes"] = payload.get("delivery_notes") or ""
        if "lines" in payload:
            values["order_line"] = self._prepare_order_line_commands(payload.get("lines") or [])
        if values:
            order.write(values)
        self._remember_mobile_request(payload, order)
        return self._ok(self._serialize_order(order, detailed=True))

    def _order_confirm(self, order_id):
        payload = self._json_body()
        replay = self._replay_mobile_request(
            payload,
            lambda record, detailed=True: self._serialize_order(record, detailed=detailed),
        )
        if replay:
            return replay
        order = self._browse_scoped("sale.order", order_id).exists()
        if not order:
            return self._error(_("Order not found."), status=404, code="not_found")
        self._ensure_current_user_owns(order, "confirm this order")
        order.with_context(**self._geo_context_from_payload(payload)).action_confirm()
        self._remember_mobile_request(payload, order)
        return self._ok(self._serialize_order(order, detailed=True))

    def _collections(self):
        limit = self._args_int("limit", 40)
        state = request.httprequest.args.get("state")
        query = (request.httprequest.args.get("query") or "").strip()
        partner_id = self._args_int("partner_id", 0)
        visit_id = self._args_int("visit_id", 0)
        invoice_id = self._args_int("invoice_id", 0)
        task_id = self._args_int("task_id", 0)
        date_from = (request.httprequest.args.get("date_from") or "").strip()
        date_to = (request.httprequest.args.get("date_to") or "").strip()
        domain = []
        if state:
            domain.append(("ftiq_collection_state", "=", state))
        if partner_id:
            domain.append(("partner_id", "=", partner_id))
        if visit_id:
            domain.append(("ftiq_visit_id", "=", visit_id))
        if invoice_id:
            domain.append(("ftiq_collection_line_ids.invoice_id", "=", invoice_id))
        if task_id:
            domain.append(("ftiq_daily_task_id", "=", task_id))
        if date_from:
            domain.append(("date", ">=", date_from))
        if date_to:
            domain.append(("date", "<=", date_to))
        if query:
            domain = expression.AND([
                domain,
                expression.OR([
                    [("display_name", "ilike", query)],
                    [("partner_id.display_name", "ilike", query)],
                    [("memo", "ilike", query)],
                    [("payment_reference", "ilike", query)],
                    [("ftiq_check_number", "ilike", query)],
                ]),
            ])
        payments = self._search_scoped(
            "account.payment",
            domain,
            order="date desc, id desc",
            limit=limit,
        )
        items = [self._serialize_collection(payment) for payment in payments]
        return self._ok({"items": items}, meta={"count": len(items)})

    def _collection_detail(self, payment_id):
        payment = self._browse_scoped("account.payment", payment_id).exists()
        if not payment:
            return self._error(_("Collection not found."), status=404, code="not_found")
        return self._ok(self._serialize_collection(payment, detailed=True))

    def _collection_create(self):
        payload = self._json_body()
        replay = self._replay_mobile_request(
            payload,
            lambda record, detailed=True: self._serialize_collection(record, detailed=detailed),
        )
        if replay:
            return replay
        visit = self._resolve_visit_from_payload(payload)
        task = self._resolve_task_from_payload(payload)
        if payload.get("visit_id") and not visit:
            return self._error(_("Visit not found."), status=404, code="not_found")
        if payload.get("task_id") and not task:
            return self._error(_("Task not found."), status=404, code="not_found")
        if visit:
            self._ensure_current_user_owns(visit, "create this collection")
        if task:
            self._ensure_current_user_owns(task, "create this collection")
        partner_id = (
            payload.get("partner_id")
            or (visit.partner_id.id if visit else False)
            or (task.partner_id.id if task else False)
        )
        if not partner_id:
            return self._error(_("partner_id is required."))
        journal, payment_method_line = self._resolve_payment_setup(payload)
        task_visit = task.visit_id if task and task.visit_id else request.env["ftiq.visit"]
        task_attendance = task_visit.attendance_id if task_visit else request.env["ftiq.field.attendance"]
        values = {
            "partner_id": partner_id,
            "amount": payload.get("amount") or 0.0,
            "date": payload.get("date") or str(fields.Date.context_today(self._current_user())),
            "payment_type": "inbound",
            "partner_type": "customer",
            "journal_id": journal.id,
            "payment_method_line_id": payment_method_line.id,
            "memo": payload.get("memo") or "",
            "payment_reference": payload.get("payment_reference") or "",
            "is_field_collection": True,
            "ftiq_user_id": self._current_user().id,
            "ftiq_visit_id": visit.id if visit else (task_visit.id if task_visit else False),
            "ftiq_attendance_id": (
                visit.attendance_id.id
                if visit and visit.attendance_id
                else (task_attendance.id if task_attendance else False)
            ),
            "ftiq_daily_task_id": (
                visit.plan_line_id.daily_task_id.id
                if visit and visit.plan_line_id.daily_task_id
                else (task.id if task else False)
            ),
            "ftiq_latitude": payload.get("latitude") or (visit.start_latitude if visit else 0.0),
            "ftiq_longitude": payload.get("longitude") or (visit.start_longitude if visit else 0.0),
            "ftiq_check_number": payload.get("check_number") or "",
            "ftiq_check_date": payload.get("check_date") or False,
            "ftiq_bank_name": payload.get("bank_name") or "",
            "ftiq_receipt_image": payload.get("receipt_image") or False,
            "ftiq_receipt_image_name": payload.get("receipt_image_name") or "",
        }
        payment = request.env["account.payment"].create(values)
        self._save_collection_payload(payment, payload)
        self._remember_mobile_request(payload, payment)
        return self._ok(self._serialize_collection(payment, detailed=True), status=201)

    def _collection_save(self, payment_id):
        payload = self._json_body()
        replay = self._replay_mobile_request(
            payload,
            lambda record, detailed=True: self._serialize_collection(record, detailed=detailed),
        )
        if replay:
            return replay
        payment = self._browse_scoped("account.payment", payment_id).exists()
        if not payment:
            return self._error(_("Collection not found."), status=404, code="not_found")
        self._ensure_current_user_owns(payment, "update this collection")
        self._save_collection_payload(payment, payload)
        self._remember_mobile_request(payload, payment)
        return self._ok(self._serialize_collection(payment, detailed=True))

    def _collection_action(self, payment_id, method_name):
        payload = self._json_body()
        replay = self._replay_mobile_request(
            payload,
            lambda record, detailed=True: self._serialize_collection(record, detailed=detailed),
        )
        if replay:
            return replay
        payment = self._browse_scoped("account.payment", payment_id).exists()
        if not payment:
            return self._error(_("Collection not found."), status=404, code="not_found")
        if method_name == "action_ftiq_verify":
            self._ensure_role({"supervisor", "manager"}, "verify this collection")
        else:
            self._ensure_current_user_owns(payment, "change this collection")
        getattr(payment.with_context(**self._geo_context_from_payload(payload)), method_name)()
        self._remember_mobile_request(payload, payment)
        return self._ok(self._serialize_collection(payment, detailed=True))

    def _stock_checks(self):
        limit = self._args_int("limit", 20)
        state = request.httprequest.args.get("state")
        partner_id = self._args_int("partner_id", 0)
        visit_id = self._args_int("visit_id", 0)
        domain = []
        if state:
            domain.append(("state", "=", state))
        if partner_id:
            domain.append(("partner_id", "=", partner_id))
        if visit_id:
            domain.append(("visit_id", "=", visit_id))
        checks = self._search_scoped(
            "ftiq.stock.check",
            domain,
            order="check_date desc, id desc",
            limit=limit,
        )
        items = [self._serialize_stock_check(check) for check in checks]
        return self._ok({"items": items}, meta={"count": len(items)})

    def _stock_check_detail(self, check_id):
        check = self._browse_scoped("ftiq.stock.check", check_id).exists()
        if not check:
            return self._error(_("Stock check not found."), status=404, code="not_found")
        return self._ok(self._serialize_stock_check(check, detailed=True))

    def _stock_check_create(self):
        payload = self._json_body()
        replay = self._replay_mobile_request(
            payload,
            lambda record, detailed=True: self._serialize_stock_check(record, detailed=detailed),
        )
        if replay:
            return replay
        visit = self._resolve_visit_from_payload(payload)
        if payload.get("visit_id") and not visit:
            return self._error(_("Visit not found."), status=404, code="not_found")
        if visit:
            self._ensure_current_user_owns(visit, "create this stock check")
        partner_id = payload.get("partner_id") or (visit.partner_id.id if visit else False)
        if not partner_id:
            return self._error(_("partner_id is required."))
        values = {
            "partner_id": partner_id,
            "user_id": self._current_user().id,
            "visit_id": visit.id if visit else False,
            "attendance_id": visit.attendance_id.id if visit and visit.attendance_id else False,
            "ftiq_daily_task_id": visit.plan_line_id.daily_task_id.id if visit and visit.plan_line_id.daily_task_id else False,
            "check_date": payload.get("check_date") or fields.Datetime.to_string(fields.Datetime.now()),
            "notes": payload.get("notes") or "",
            "latitude": payload.get("latitude") or (visit.end_latitude or visit.start_latitude if visit else 0.0),
            "longitude": payload.get("longitude") or (visit.end_longitude or visit.start_longitude if visit else 0.0),
            "photo": payload.get("photo") or False,
            "photo_name": payload.get("photo_name") or "",
            "line_ids": self._prepare_stock_line_commands(payload.get("lines") or []),
        }
        check = request.env["ftiq.stock.check"].create(values)
        self._remember_mobile_request(payload, check)
        return self._ok(self._serialize_stock_check(check, detailed=True), status=201)

    def _stock_check_save(self, check_id):
        payload = self._json_body()
        replay = self._replay_mobile_request(
            payload,
            lambda record, detailed=True: self._serialize_stock_check(record, detailed=detailed),
        )
        if replay:
            return replay
        check = self._browse_scoped("ftiq.stock.check", check_id).exists()
        if not check:
            return self._error(_("Stock check not found."), status=404, code="not_found")
        self._ensure_current_user_owns(check, "update this stock check")
        values = {}
        if "notes" in payload:
            values["notes"] = payload.get("notes") or ""
        if "latitude" in payload:
            values["latitude"] = payload.get("latitude") or 0.0
        if "longitude" in payload:
            values["longitude"] = payload.get("longitude") or 0.0
        if "check_date" in payload:
            values["check_date"] = payload.get("check_date") or fields.Datetime.to_string(fields.Datetime.now())
        if "photo" in payload:
            values["photo"] = payload.get("photo") or False
        if "photo_name" in payload:
            values["photo_name"] = payload.get("photo_name") or ""
        if "lines" in payload:
            values["line_ids"] = self._prepare_stock_line_commands(payload.get("lines") or [])
        if values:
            check.write(values)
        self._remember_mobile_request(payload, check)
        return self._ok(self._serialize_stock_check(check, detailed=True))

    def _stock_check_action(self, check_id, method_name):
        payload = self._json_body()
        replay = self._replay_mobile_request(
            payload,
            lambda record, detailed=True: self._serialize_stock_check(record, detailed=detailed),
        )
        if replay:
            return replay
        check = self._browse_scoped("ftiq.stock.check", check_id).exists()
        if not check:
            return self._error(_("Stock check not found."), status=404, code="not_found")
        if method_name in {"action_review", "action_reset_draft"}:
            self._ensure_role({"supervisor", "manager"}, "review this stock check")
        else:
            self._ensure_current_user_owns(check, "change this stock check")
        getattr(check.with_context(**self._geo_context_from_payload(payload)), method_name)()
        self._remember_mobile_request(payload, check)
        return self._ok(self._serialize_stock_check(check, detailed=True))

    def _resolve_visit_from_payload(self, payload):
        visit_id = payload.get("visit_id")
        if not visit_id:
            return request.env["ftiq.visit"]
        return self._browse_scoped("ftiq.visit", visit_id).exists()

    def _resolve_task_from_payload(self, payload):
        task_id = payload.get("task_id")
        if not task_id:
            return request.env["ftiq.daily.task"]
        return self._browse_scoped("ftiq.daily.task", task_id).exists()

    def _resolve_plan_line_from_payload(self, payload):
        plan_line_id = payload.get("plan_line_id")
        if not plan_line_id:
            return request.env["ftiq.weekly.plan.line"]
        return self._browse_scoped("ftiq.weekly.plan.line", plan_line_id).exists()

    def _get_open_invoices_for_partner(self, partner):
        return self._search_scoped("account.move", [
            ("partner_id", "child_of", partner.commercial_partner_id.id),
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
        ], order="invoice_date_due asc, invoice_date asc, id asc")

    def _save_visit_payload(self, visit, payload):
        values = {}
        for field_name in ("outcome", "general_feedback", "unplanned_reason"):
            if field_name in payload:
                values[field_name] = payload.get(field_name) or False
        for field_name in ("photo_1", "photo_2", "photo_3", "signature"):
            if field_name in payload:
                values[field_name] = payload.get(field_name) or False
        if "product_lines" in payload:
            values["product_line_ids"] = self._prepare_visit_product_commands(payload.get("product_lines") or [])
        if values:
            visit.write(values)
        if "material_logs" in payload:
            visit.write({
                "material_view_log_ids": self._prepare_material_log_commands(
                    visit,
                    payload.get("material_logs") or [],
                ),
            })

    def _prepare_visit_product_commands(self, items):
        commands = [Command.clear()]
        for index, item in enumerate(items, start=1):
            product_id = item.get("product_id")
            if not product_id:
                continue
            commands.append(Command.create({
                "product_id": product_id,
                "call_reason_id": item.get("call_reason_id") or False,
                "detail_notes": item.get("detail_notes") or "",
                "outcome": item.get("outcome") or False,
                "samples_distributed": item.get("samples_distributed") or 0,
                "stock_on_hand": item.get("stock_on_hand") or 0,
                "feedback": item.get("feedback") or "",
                "sequence": item.get("sequence") or (index * 10),
            }))
        return commands

    def _prepare_material_log_commands(self, visit, items):
        commands = [Command.clear()]
        product_lines_by_product = {}
        for line in visit.product_line_ids:
            product_lines_by_product.setdefault(line.product_id.id, line)
        for item in items:
            material_id = item.get("material_id")
            if not material_id:
                continue
            start_time = item.get("start_time")
            end_time = item.get("end_time")
            duration_minutes = self._duration_minutes_from_payload(item)
            if start_time and not end_time and duration_minutes:
                end_time = fields.Datetime.to_string(
                    fields.Datetime.to_datetime(start_time) + timedelta(minutes=duration_minutes)
                )
            if not start_time and duration_minutes:
                generated_start = fields.Datetime.now()
                start_time = fields.Datetime.to_string(generated_start)
                end_time = fields.Datetime.to_string(generated_start + timedelta(minutes=duration_minutes))
            product_line = False
            if item.get("product_line_id"):
                product_line = visit.product_line_ids.filtered(lambda line: line.id == item.get("product_line_id"))[:1]
            if not product_line and item.get("product_id"):
                product_line = product_lines_by_product.get(item.get("product_id"))
            commands.append(Command.create({
                "product_line_id": product_line.id if product_line else False,
                "material_id": material_id,
                "start_time": start_time or False,
                "end_time": end_time or False,
                "note": item.get("note") or "",
            }))
        return commands

    def _duration_minutes_from_payload(self, item):
        value = item.get("duration_minutes")
        if value in (None, ""):
            return 0
        try:
            return max(int(float(value)), 0)
        except Exception:
            return 0

    def _prepare_order_line_commands(self, items):
        commands = [Command.clear()]
        for item in items:
            product_id = item.get("product_id")
            quantity = item.get("quantity")
            if not product_id or quantity in (None, "", 0):
                continue
            values = {
                "product_id": product_id,
                "product_uom_qty": quantity,
            }
            if item.get("price_unit") not in (None, ""):
                values["price_unit"] = item.get("price_unit")
            if item.get("discount") not in (None, ""):
                values["discount"] = item.get("discount")
            commands.append(Command.create(values))
        return commands

    def _resolve_payment_setup(self, payload):
        journal_id = payload.get("journal_id")
        domain = [
            ("company_id", "=", self._current_user().company_id.id),
            ("type", "in", ("bank", "cash")),
            ("active", "=", True),
        ]
        if journal_id:
            domain.append(("id", "=", journal_id))
        journal = request.env["account.journal"].search(
            domain,
            order="sequence, id",
            limit=1,
        )
        if not journal:
            raise ValidationError(_("No inbound payment journal is configured."))
        payment_method_line_id = payload.get("payment_method_line_id")
        available_lines = journal._get_available_payment_method_lines("inbound")
        if payment_method_line_id:
            payment_method_line = available_lines.filtered(lambda line: line.id == payment_method_line_id)[:1]
        else:
            payment_method_line = available_lines[:1]
        if not payment_method_line:
            raise ValidationError(_("No inbound payment method is configured for the selected journal."))
        return journal, payment_method_line

    def _save_collection_payload(self, payment, payload):
        values = {}
        if "amount" in payload:
            values["amount"] = payload.get("amount") or 0.0
        if "date" in payload:
            values["date"] = payload.get("date") or str(fields.Date.context_today(self._current_user()))
        if "memo" in payload:
            values["memo"] = payload.get("memo") or ""
        if "payment_reference" in payload:
            values["payment_reference"] = payload.get("payment_reference") or ""
        if "check_number" in payload:
            values["ftiq_check_number"] = payload.get("check_number") or ""
        if "check_date" in payload:
            values["ftiq_check_date"] = payload.get("check_date") or False
        if "bank_name" in payload:
            values["ftiq_bank_name"] = payload.get("bank_name") or ""
        if "receipt_image" in payload:
            values["ftiq_receipt_image"] = payload.get("receipt_image") or False
        if "receipt_image_name" in payload:
            values["ftiq_receipt_image_name"] = payload.get("receipt_image_name") or ""
        if "journal_id" in payload or "payment_method_line_id" in payload:
            journal, payment_method_line = self._resolve_payment_setup(payload)
            values["journal_id"] = journal.id
            values["payment_method_line_id"] = payment_method_line.id
        if "allocations" in payload:
            values["ftiq_collection_line_ids"] = self._prepare_collection_line_commands(payload.get("allocations") or [])
        if values:
            payment.write(values)
        if "allocations" not in payload and payload.get("auto_allocate") and payment.partner_id:
            payment.action_ftiq_reload_invoices()
            payment.action_ftiq_distribute_amount()

    def _prepare_collection_line_commands(self, items):
        commands = [Command.clear()]
        for item in items:
            invoice_id = item.get("invoice_id")
            if not invoice_id:
                continue
            commands.append(Command.create({
                "invoice_id": invoice_id,
                "allocated_amount": item.get("allocated_amount") or 0.0,
            }))
        return commands

    def _prepare_stock_line_commands(self, items):
        commands = [Command.clear()]
        for index, item in enumerate(items, start=1):
            product_id = item.get("product_id")
            if not product_id:
                continue
            commands.append(Command.create({
                "product_id": product_id,
                "stock_qty": item.get("stock_qty") or 0.0,
                "expiry_date": item.get("expiry_date") or False,
                "batch_number": item.get("batch_number") or "",
                "shelf_position": item.get("shelf_position") or "",
                "competitor_product": item.get("competitor_product") or "",
                "competitor_qty": item.get("competitor_qty") or 0.0,
                "note": item.get("note") or "",
                "sequence": item.get("sequence") or (index * 10),
            }))
        return commands
