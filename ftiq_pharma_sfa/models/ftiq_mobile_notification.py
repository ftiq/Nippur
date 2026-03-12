import json
import logging

from psycopg2 import IntegrityError

from odoo import api, fields, models


_logger = logging.getLogger(__name__)


class FtiqMobileNotification(models.Model):
    _name = "ftiq.mobile.notification"
    _description = "FTIQ Mobile Notification"
    _order = "is_read asc, create_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(required=True, index=True)
    body = fields.Text(required=True)
    category = fields.Selection(
        [
            ("activity", "Activity"),
            ("team", "Team"),
            ("task", "Task"),
            ("visit", "Visit"),
            ("plan", "Plan"),
            ("order", "Order"),
            ("purchase", "Purchase"),
            ("collection", "Collection"),
            ("invoice", "Invoice"),
            ("expense", "Expense"),
            ("stock_check", "Stock Check"),
            ("finance", "Finance"),
            ("system", "System"),
        ],
        required=True,
        default="system",
        index=True,
    )
    priority = fields.Selection(
        [
            ("normal", "Normal"),
            ("urgent", "Urgent"),
        ],
        required=True,
        default="normal",
        index=True,
    )
    user_id = fields.Many2one("res.users", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", required=True, index=True, ondelete="cascade")
    author_id = fields.Many2one("res.users", index=True, ondelete="set null")
    source_model = fields.Char(index=True)
    source_res_id = fields.Integer(index=True)
    target_model = fields.Char(index=True)
    target_res_id = fields.Integer(index=True)
    target_name = fields.Char()
    deep_link = fields.Char()
    event_key = fields.Char(index=True)
    is_read = fields.Boolean(default=False, index=True)
    read_date = fields.Datetime()
    payload_json = fields.Text()

    _sql_constraints = [
        (
            "ftiq_mobile_notification_event_key_unique",
            "unique(user_id, event_key)",
            "Duplicate notification event key.",
        ),
    ]

    @api.model
    def _record_identity(self, record):
        if not record:
            return "", 0, ""
        return record._name, record.id, record.display_name

    @api.model
    def _company_for(self, user=False, target=False, source=False, author=False):
        for record in (target, source, user, author, self.env.user):
            company = getattr(record, "company_id", False)
            if company:
                return company
        return self.env.company

    @api.model
    def _payload_json(self, payload):
        try:
            return json.dumps(payload or {}, ensure_ascii=False)
        except Exception:
            return "{}"

    def _payload_map(self):
        self.ensure_one()
        try:
            value = json.loads(self.payload_json or "{}")
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    @api.model
    def category_for_model(self, model_name, default="system"):
        return {
            "ftiq.daily.task": "task",
            "ftiq.visit": "visit",
            "ftiq.weekly.plan": "plan",
            "sale.order": "order",
            "purchase.order": "purchase",
            "project.task": "task",
            "account.payment": "collection",
            "account.move": "invoice",
            "hr.expense": "expense",
            "ftiq.stock.check": "stock_check",
        }.get((model_name or "").strip(), default)

    @api.model
    def build_target_deep_link(self, target_model="", target_res_id=0, notification_id=False):
        query = f"notification_id={notification_id}" if notification_id else ""

        def with_query(base_link):
            if not query:
                return base_link
            joiner = "&" if "?" in base_link else "?"
            return f"{base_link}{joiner}{query}"

        if target_model == "ftiq.daily.task" and target_res_id:
            return with_query(f"ftiq://task?id={target_res_id}")
        if target_model == "ftiq.visit" and target_res_id:
            return with_query(f"ftiq://visit?id={target_res_id}")
        if target_model == "ftiq.weekly.plan" and target_res_id:
            return with_query(f"ftiq://plan?id={target_res_id}")
        if target_model == "sale.order" and target_res_id:
            return with_query(f"ftiq://order?id={target_res_id}")
        if target_model == "purchase.order" and target_res_id:
            return with_query(f"ftiq://purchase?id={target_res_id}")
        if target_model == "project.task" and target_res_id:
            return with_query(f"ftiq://project-task?id={target_res_id}")
        if target_model == "account.move" and target_res_id:
            return with_query(f"ftiq://invoice?id={target_res_id}")
        if target_model == "account.payment" and target_res_id:
            return with_query(f"ftiq://collection?id={target_res_id}")
        if target_model == "hr.expense" and target_res_id:
            return with_query(f"ftiq://expense?id={target_res_id}")
        if target_model == "ftiq.stock.check" and target_res_id:
            return with_query(f"ftiq://stock-check?id={target_res_id}")
        if target_model == "ftiq.team.message" and target_res_id:
            return with_query(f"ftiq://notifications?message_id={target_res_id}")
        return with_query("ftiq://notifications")

    def _build_deep_link(self):
        self.ensure_one()
        return self.build_target_deep_link(
            target_model=self.target_model,
            target_res_id=self.target_res_id,
            notification_id=self.id,
        )

    def _push_payload(self):
        self.ensure_one()
        payload = self._payload_map()
        payload.update(
            {
                "deep_link": self.deep_link or self._build_deep_link(),
                "notification_id": self.id,
                "category": self.category or "",
                "priority": self.priority or "",
                "target_model": self.target_model or "",
                "target_id": self.target_res_id or "",
                "source_model": self.source_model or "",
                "source_id": self.source_res_id or "",
            }
        )
        return payload

    def _dispatch_push(self):
        push_service = self.env["ftiq.firebase.push.service"]
        device_model = self.env["ftiq.mobile.device"].sudo()
        for notification in self:
            devices = device_model.search(
                [
                    ("company_id", "=", notification.company_id.id),
                    ("user_id", "=", notification.user_id.id),
                    ("state", "=", "active"),
                    ("push_token", "!=", False),
                ]
            )
            if not devices:
                continue
            push_service.send_to_devices(
                devices,
                title=notification.name,
                body=notification.body,
                data=notification._push_payload(),
                priority=notification.priority or "normal",
            )

    @api.model
    def approval_users_for(self, record):
        team = getattr(record, "team_id", False)
        company = self._company_for(target=record)
        users = self.env["res.users"]
        if team and team.user_id:
            users |= team.user_id
        manager_group = self.env.ref("ftiq_pharma_sfa.group_ftiq_manager", raise_if_not_found=False)
        if manager_group:
            users |= manager_group.users
        return users.filtered(lambda user: not user.share and user.company_id == company)

    @api.model
    def owner_user_for(self, record):
        for field_name in ("user_id", "ftiq_user_id", "target_user_id"):
            user = getattr(record, field_name, False)
            if user:
                return user
        return self.env["res.users"]

    @api.model
    def sync_live_activities_for_user(self, user=False):
        target_user = user if user else self.env.user
        if not target_user or not target_user.id:
            return self.browse()
        activities = self.env["mail.activity"].search(
            [
                ("user_id", "=", target_user.id),
                ("active", "=", True),
            ]
        )
        if activities:
            activities._sync_mobile_notifications()
        return activities

    @api.model
    def sync_live_mail_notifications_for_user(self, user=False, limit=120):
        target_user = user if user else self.env.user
        partner = target_user.partner_id if target_user else self.env["res.partner"]
        if not partner or not partner.id:
            return self.env["mail.notification"]
        notifications = self.env["mail.notification"].search(
            [
                ("res_partner_id", "=", partner.id),
                ("notification_type", "=", "inbox"),
                ("notification_status", "not in", ("bounce", "exception")),
                (
                    "mail_message_id.model",
                    "in",
                    [
                        "ftiq.daily.task",
                        "ftiq.visit",
                        "ftiq.weekly.plan",
                        "sale.order",
                        "purchase.order",
                        "project.task",
                        "account.payment",
                        "account.move",
                        "hr.expense",
                        "ftiq.stock.check",
                    ],
                ),
            ],
            order="mail_message_id desc, res_partner_id desc",
            limit=limit,
        )
        if notifications:
            notifications._sync_mobile_notifications()
        return notifications

    @api.model
    def create_for_users(
        self,
        users,
        *,
        title,
        body,
        category,
        priority="normal",
        target=False,
        source=False,
        author=False,
        payload=None,
        event_key="",
    ):
        valid_users = users.exists().filtered(lambda user: not user.share)
        if not valid_users:
            return self.browse()
        author_user = author if author else self.env.user
        records = self.browse()
        push_records = self.browse()
        target_model, target_res_id, target_name = self._record_identity(target)
        source_model, source_res_id, _source_name = self._record_identity(source)
        for user in valid_users:
            company = self._company_for(user=user, target=target, source=source, author=author_user)
            search_domain = [
                ("user_id", "=", user.id),
                ("event_key", "=", event_key),
            ] if event_key else []
            values = {
                "name": title,
                "body": body,
                "category": category,
                "priority": priority or "normal",
                "user_id": user.id,
                "company_id": company.id,
                "author_id": author_user.id if author_user else False,
                "source_model": source_model,
                "source_res_id": source_res_id,
                "target_model": target_model,
                "target_res_id": target_res_id,
                "target_name": target_name,
                "payload_json": self._payload_json(payload),
                "event_key": event_key or False,
                "is_read": False,
                "read_date": False,
            }
            record = self.browse()
            should_push = False
            for attempt in range(2):
                try:
                    with self.env.cr.savepoint():
                        existing = self.sudo().search(search_domain, limit=1) if search_domain else self.browse()
                        if existing:
                            record = existing
                            if not self._skip_existing_upsert(existing, values):
                                update_values = self._notification_update_values(existing, values)
                                if update_values:
                                    existing.sudo().write(update_values)
                                    should_push = True
                        else:
                            try:
                                record = self.sudo().create(values)
                                should_push = True
                            except IntegrityError:
                                if not search_domain:
                                    raise
                                record = self.sudo().search(search_domain, limit=1)
                                if not record:
                                    raise
                                update_values = self._notification_update_values(record, values)
                                if update_values:
                                    record.sudo().write(update_values)
                                    should_push = True
                    break
                except Exception as error:
                    if attempt >= 1 or not self._is_retryable_notification_error(error):
                        raise
                    _logger.warning(
                        "FTIQ mobile notification upsert retry for event %s user %s after %s",
                        event_key,
                        user.id,
                        error.__class__.__name__,
                    )
            deep_link = record._build_deep_link()
            if record.deep_link != deep_link:
                with self.env.cr.savepoint():
                    record.sudo().write({"deep_link": deep_link})
                should_push = True
            records |= record
            if should_push and not self.env.context.get("ftiq_skip_push_dispatch"):
                push_records |= record
        push_records._dispatch_push()
        return records

    def _skip_existing_upsert(self, record, values):
        source_model = (values.get("source_model") or "").strip()
        if source_model in {"mail.activity", "mail.notification"}:
            return True
        return False

    def _notification_update_values(self, record, values):
        update_values = {}
        for field_name, value in values.items():
            if field_name in {"is_read", "read_date"}:
                continue
            field = record._fields.get(field_name)
            if not field:
                continue
            current_value = record[field_name]
            if field.type == "many2one":
                current_value = current_value.id or False
            if current_value != value:
                update_values[field_name] = value
        return update_values

    def _is_retryable_notification_error(self, error):
        return error.__class__.__name__ in {"SerializationFailure", "DeadlockDetected"}

    def action_mark_read(self):
        unread = self.filtered(lambda notification: not notification.is_read)
        if unread:
            unread.write(
                {
                    "is_read": True,
                    "read_date": fields.Datetime.now(),
                }
            )
        return True
