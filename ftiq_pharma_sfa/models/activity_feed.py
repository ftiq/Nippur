from odoo import _, fields, models


FTIQ_ACTIVITY_PAYMENT_STATES = ("in_process", "paid")
FTIQ_ACTIVITY_TERMINAL_TASK_STATES = ("completed", "confirmed", "cancelled")


class FtiqActivityFeed(models.AbstractModel):
    _name = "ftiq.activity.feed"
    _description = "FTIQ Unified Activity Feed"

    def build_feed(self, scope_user_ids, limit=12, include_invoices=True):
        scope_user_ids = list(scope_user_ids or [])
        items = []
        items += self._build_task_items(scope_user_ids)
        items += self._build_visit_items(scope_user_ids)
        items += self._build_order_items(scope_user_ids)
        items += self._build_collection_items(scope_user_ids)
        items += self._build_stock_check_items(scope_user_ids)
        items += self._build_expense_items(scope_user_ids)
        if include_invoices:
            items += self._build_invoice_items(scope_user_ids)
        items.sort(key=lambda item: item["sort_datetime"] or "", reverse=True)
        return items[:limit]

    def _build_task_items(self, scope_user_ids):
        records = self.env["ftiq.daily.task"].search([
            ("user_id", "in", scope_user_ids),
            ("state", "not in", FTIQ_ACTIVITY_TERMINAL_TASK_STATES),
        ], order="scheduled_date desc, id desc", limit=10)
        return [self._serialize_task(record) for record in records]

    def _build_visit_items(self, scope_user_ids):
        records = self.env["ftiq.visit"].search([
            ("user_id", "in", scope_user_ids),
        ], order="write_date desc, id desc", limit=10)
        return [self._serialize_visit(record) for record in records]

    def _build_order_items(self, scope_user_ids):
        records = self.env["sale.order"].search([
            ("user_id", "in", scope_user_ids),
            ("is_field_order", "=", True),
        ], order="write_date desc, id desc", limit=10)
        return [self._serialize_order(record) for record in records]

    def _build_collection_items(self, scope_user_ids):
        records = self.env["account.payment"].search([
            ("ftiq_user_id", "in", scope_user_ids),
            ("is_field_collection", "=", True),
        ], order="write_date desc, id desc", limit=10)
        return [self._serialize_collection(record) for record in records]

    def _build_stock_check_items(self, scope_user_ids):
        records = self.env["ftiq.stock.check"].search([
            ("user_id", "in", scope_user_ids),
        ], order="write_date desc, id desc", limit=10)
        return [self._serialize_stock_check(record) for record in records]

    def _build_expense_items(self, scope_user_ids):
        records = self.env["hr.expense"].search([
            ("is_field_expense", "=", True),
            ("ftiq_user_id", "in", scope_user_ids),
        ], order="write_date desc, id desc", limit=10)
        return [self._serialize_expense(record) for record in records]

    def _build_invoice_items(self, scope_user_ids):
        records = self.env["account.move"].search([
            ("ftiq_access_user_id", "in", scope_user_ids),
            ("is_field_invoice", "=", True),
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
        ], order="invoice_date_due asc, invoice_date asc, id desc", limit=8)
        return [self._serialize_invoice(record) for record in records]

    def _serialize_task(self, record):
        linked = []
        if record.visit_id:
            linked.append(_("Visit"))
        if record.sale_order_id:
            linked.append(_("Order"))
        if record.payment_id:
            linked.append(_("Collection"))
        if record.stock_check_id:
            linked.append(_("Stock Check"))
        return self._base_item(
            record_model=record._name,
            record_id=record.id,
            item_type="task",
            item_type_label=_("Task"),
            reference=record.name,
            partner_name=record.partner_id.display_name,
            user_name=record.user_id.name,
            status=record.state,
            status_label=self._label_for_task_state(record.state),
            item_datetime=record.completed_date or record.scheduled_date,
            amount=False,
            secondary=_("%s profile") % (record.task_profile_id.display_name or record.task_type),
            geo_url=self._build_geo_url(record.latitude, record.longitude),
            linked_documents=linked,
        )

    def _serialize_visit(self, record):
        linked = []
        if record.sale_order_count:
            linked.append(_("%s order(s)") % record.sale_order_count)
        if record.payment_count:
            linked.append(_("%s collection(s)") % record.payment_count)
        if record.stock_check_count:
            linked.append(_("%s stock check(s)") % record.stock_check_count)
        visit_datetime = record.end_time or record.start_time or fields.Datetime.to_string(
            fields.Datetime.to_datetime(record.visit_date)
        )
        return self._base_item(
            record_model=record._name,
            record_id=record.id,
            item_type="visit",
            item_type_label=_("Visit"),
            reference=record.name,
            partner_name=record.partner_id.display_name,
            user_name=record.user_id.name,
            status=record.state,
            status_label=self._label_for_visit_state(record.state),
            item_datetime=visit_datetime,
            amount=False,
            secondary=record.outcome and dict(record._fields["outcome"].selection).get(record.outcome) or "",
            geo_url=self._build_geo_url(
                record.end_latitude or record.start_latitude,
                record.end_longitude or record.start_longitude,
            ),
            linked_documents=linked,
        )

    def _serialize_order(self, record):
        linked = []
        if record.ftiq_visit_id:
            linked.append(record.ftiq_visit_id.display_name)
        if record.ftiq_daily_task_id:
            linked.append(record.ftiq_daily_task_id.display_name)
        return self._base_item(
            record_model=record._name,
            record_id=record.id,
            item_type="order",
            item_type_label=_("Order"),
            reference=record.name,
            partner_name=record.partner_id.display_name,
            user_name=record.user_id.name,
            status=record.state,
            status_label=self._label_for_order_state(record.state),
            item_datetime=record.date_order,
            amount=record.amount_total,
            secondary=dict(record._fields["ftiq_priority"].selection).get(record.ftiq_priority) if record.ftiq_priority else "",
            geo_url=self._build_geo_url(record.ftiq_latitude, record.ftiq_longitude),
            linked_documents=linked,
        )

    def _serialize_collection(self, record):
        linked = []
        if record.ftiq_visit_id:
            linked.append(record.ftiq_visit_id.display_name)
        if record.ftiq_daily_task_id:
            linked.append(record.ftiq_daily_task_id.display_name)
        if record.ftiq_open_invoice_count:
            linked.append(_("%s open invoice(s)") % record.ftiq_open_invoice_count)
        status = record.ftiq_collection_state or record.state
        reference = record.name or record.payment_reference or record.memo or record.display_name or _("Collection")
        return self._base_item(
            record_model=record._name,
            record_id=record.id,
            item_type="collection",
            item_type_label=_("Collection"),
            reference=reference,
            partner_name=record.partner_id.display_name,
            user_name=record.ftiq_user_id.name,
            status=status,
            status_label=self._label_for_collection_state(status),
            item_datetime=record.write_date or record.create_date,
            amount=record.amount,
            secondary=record.journal_id.display_name or "",
            geo_url=self._build_geo_url(record.ftiq_latitude, record.ftiq_longitude),
            linked_documents=linked,
        )

    def _serialize_stock_check(self, record):
        linked = []
        if record.visit_id:
            linked.append(record.visit_id.display_name)
        if record.ftiq_daily_task_id:
            linked.append(record.ftiq_daily_task_id.display_name)
        return self._base_item(
            record_model=record._name,
            record_id=record.id,
            item_type="stock",
            item_type_label=_("Stock Check"),
            reference=record.name,
            partner_name=record.partner_id.display_name,
            user_name=record.user_id.name,
            status=record.state,
            status_label=self._label_for_stock_state(record.state),
            item_datetime=record.check_date,
            amount=False,
            secondary=_("%s line(s)") % len(record.line_ids),
            geo_url=self._build_geo_url(record.latitude, record.longitude),
            linked_documents=linked,
        )

    def _serialize_expense(self, record):
        linked = []
        if record.ftiq_visit_id:
            linked.append(record.ftiq_visit_id.display_name)
        if record.ftiq_daily_task_id:
            linked.append(record.ftiq_daily_task_id.display_name)
        return self._base_item(
            record_model=record._name,
            record_id=record.id,
            item_type="expense",
            item_type_label=_("Expense"),
            reference=record.name or record.product_id.display_name or _("Expense"),
            partner_name=record.ftiq_partner_id.display_name,
            user_name=record.ftiq_user_id.name or record.employee_id.user_id.name,
            status=record.state,
            status_label=self._label_for_expense_state(record.state),
            item_datetime=record.date,
            amount=record.total_amount or record.total_amount_company,
            secondary=dict(record._fields["ftiq_expense_type"].selection).get(record.ftiq_expense_type) if record.ftiq_expense_type else "",
            geo_url=self._build_geo_url(record.ftiq_latitude, record.ftiq_longitude),
            linked_documents=linked,
        )

    def _serialize_invoice(self, record):
        linked = []
        if record.ftiq_visit_id:
            linked.append(record.ftiq_visit_id.display_name)
        if record.ftiq_daily_task_id:
            linked.append(record.ftiq_daily_task_id.display_name)
        return self._base_item(
            record_model=record._name,
            record_id=record.id,
            item_type="invoice",
            item_type_label=_("Invoice"),
            reference=record.name,
            partner_name=record.partner_id.display_name,
            user_name=record.ftiq_user_id.name or record.invoice_user_id.name,
            status=record.payment_state,
            status_label=self._label_for_invoice_state(record.payment_state),
            item_datetime=record.invoice_date_due or record.invoice_date,
            amount=record.amount_residual,
            secondary=_("Residual due"),
            geo_url=False,
            linked_documents=linked,
        )

    def _base_item(
        self,
        record_model,
        record_id,
        item_type,
        item_type_label,
        reference,
        partner_name,
        user_name,
        status,
        status_label,
        item_datetime,
        amount,
        secondary,
        geo_url,
        linked_documents,
    ):
        return {
            "record_model": record_model,
            "record_id": record_id,
            "type": item_type,
            "type_label": item_type_label,
            "reference": reference or "",
            "partner_name": partner_name or "",
            "user_name": user_name or "",
            "status": status or "",
            "status_label": status_label or status or "",
            "datetime": fields.Datetime.to_string(fields.Datetime.to_datetime(item_datetime)) if item_datetime else "",
            "sort_datetime": fields.Datetime.to_string(fields.Datetime.to_datetime(item_datetime)) if item_datetime else "",
            "amount": amount or 0.0,
            "secondary": secondary or "",
            "geo_url": geo_url or "",
            "linked_documents": linked_documents or [],
        }

    @staticmethod
    def _build_geo_url(latitude, longitude):
        if not latitude or not longitude:
            return False
        return "https://www.google.com/maps?q=%s,%s" % (latitude, longitude)

    @staticmethod
    def _label_for_task_state(state):
        return {
            "draft": _("Draft"),
            "pending": _("Pending"),
            "in_progress": _("In Progress"),
            "completed": _("Completed"),
            "submitted": _("Submitted"),
            "confirmed": _("Confirmed"),
            "returned": _("Returned"),
            "cancelled": _("Cancelled"),
        }.get(state, state)

    @staticmethod
    def _label_for_visit_state(state):
        return {
            "draft": _("Draft"),
            "in_progress": _("In Progress"),
            "submitted": _("Submitted"),
            "approved": _("Approved"),
            "returned": _("Returned"),
        }.get(state, state)

    @staticmethod
    def _label_for_order_state(state):
        return {
            "draft": _("Quotation"),
            "sent": _("Quotation Sent"),
            "sale": _("Confirmed"),
            "done": _("Locked"),
            "cancel": _("Cancelled"),
        }.get(state, state)

    @staticmethod
    def _label_for_collection_state(state):
        return {
            "draft": _("Draft"),
            "collected": _("Collected"),
            "deposited": _("Deposited"),
            "verified": _("Verified"),
            "in_process": _("Posted"),
            "paid": _("Paid"),
        }.get(state, state)

    @staticmethod
    def _label_for_stock_state(state):
        return {
            "draft": _("Draft"),
            "submitted": _("Submitted"),
            "reviewed": _("Reviewed"),
        }.get(state, state)

    @staticmethod
    def _label_for_expense_state(state):
        return {
            "draft": _("Draft"),
            "reported": _("Reported"),
            "approved": _("Approved"),
            "done": _("Posted"),
            "refused": _("Refused"),
        }.get(state, state)

    @staticmethod
    def _label_for_invoice_state(state):
        return {
            "not_paid": _("Unpaid"),
            "in_payment": _("In Payment"),
            "paid": _("Paid"),
            "partial": _("Partially Paid"),
            "reversed": _("Reversed"),
            "invoicing_legacy": _("Legacy"),
        }.get(state, state)
