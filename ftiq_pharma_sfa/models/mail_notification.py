from odoo import _, api, models
from odoo.tools.mail import html2plaintext


class MailNotification(models.Model):
    _inherit = "mail.notification"

    _FTIQ_MOBILE_SUPPORTED_MODELS = {
        "ftiq.daily.task",
        "ftiq.visit",
        "ftiq.weekly.plan",
        "project.project",
        "sale.order",
        "purchase.order",
        "project.task",
        "account.payment",
        "account.move",
        "hr.expense",
        "ftiq.stock.check",
    }

    def _mobile_target_record(self):
        self.ensure_one()
        message = self.mail_message_id
        if (
            not message
            or not message.model
            or not message.res_id
            or message.model not in self._FTIQ_MOBILE_SUPPORTED_MODELS
        ):
            return self.env["mail.message"]
        try:
            return self.env[message.model].browse(message.res_id).exists()
        except Exception:
            return self.env["mail.message"]

    def _mobile_recipient_users(self):
        self.ensure_one()
        return self.res_partner_id.user_ids.filtered(
            lambda user: not user.share and user.active
        )

    def _mobile_author_user(self):
        self.ensure_one()
        author_users = self.mail_message_id.author_id.user_ids.filtered(
            lambda user: not user.share and user.active
        )
        return author_users[:1]

    def _mobile_notification_title(self):
        self.ensure_one()
        message = self.mail_message_id
        subject = (message.subject or "").strip()
        if subject:
            return subject
        author_name = (
            message.author_id.display_name
            or message.email_from
            or self.env.user.display_name
        )
        target_name = message.record_name or self._mobile_target_record().display_name or ""
        if author_name and target_name:
            return _("%(author)s on %(record)s") % {
                "author": author_name,
                "record": target_name,
            }
        if target_name:
            return target_name
        return _("Record update")

    def _mobile_notification_body(self):
        self.ensure_one()
        message = self.mail_message_id
        body = html2plaintext(message.body or "").strip()
        preview = (message.preview or "").strip()
        return body or preview or self._mobile_notification_title()

    def _mobile_notification_payload(self):
        self.ensure_one()
        message = self.mail_message_id
        return {
            "message_type": message.message_type or "",
            "mail_message_id": message.id,
            "mail_notification_id": self.id,
            "target_model": message.model or "",
            "target_id": message.res_id or "",
            "subtype_id": message.subtype_id.id or "",
            "subtype_name": message.subtype_id.display_name or "",
        }

    def _mobile_notification_event_key(self):
        self.ensure_one()
        return f"mail_notification:{self.id}"

    def _mobile_should_sync(self):
        self.ensure_one()
        message = self.mail_message_id
        return bool(
            self.notification_type == "inbox"
            and self.res_partner_id
            and message
            and message.model in self._FTIQ_MOBILE_SUPPORTED_MODELS
        )

    def _mobile_existing_notifications(self):
        event_keys = [notification._mobile_notification_event_key() for notification in self]
        if not event_keys:
            return self.env["ftiq.mobile.notification"]
        return self.env["ftiq.mobile.notification"].sudo().search(
            [("event_key", "in", event_keys)]
        )

    def _sync_mobile_notifications(self):
        notification_model = self.env["ftiq.mobile.notification"]
        existing_notifications = self._mobile_existing_notifications()
        existing_by_key = {
            notification.event_key: notification
            for notification in existing_notifications
            if notification.event_key
        }
        for notification in self:
            event_key = notification._mobile_notification_event_key()
            mirrored = existing_by_key.get(event_key, self.env["ftiq.mobile.notification"])
            if not notification._mobile_should_sync():
                if mirrored:
                    mirrored.action_mark_read()
                continue
            recipient_users = notification._mobile_recipient_users()
            if not recipient_users:
                if mirrored:
                    mirrored.action_mark_read()
                continue
            target = notification._mobile_target_record()
            if not target:
                if mirrored:
                    mirrored.action_mark_read()
                continue
            if notification.is_read or notification.notification_status == "canceled":
                if mirrored:
                    mirrored.action_mark_read()
                continue
            author_user = notification._mobile_author_user()
            created = notification_model.create_for_users(
                recipient_users,
                title=notification._mobile_notification_title(),
                body=notification._mobile_notification_body(),
                category=notification_model.category_for_model(
                    notification.mail_message_id.model,
                    default="system",
                ),
                priority="normal",
                target=target,
                source=notification.mail_message_id,
                author=author_user or self.env.user,
                payload=notification._mobile_notification_payload(),
                event_key=event_key,
            )
            if notification.is_read and created:
                created.action_mark_read()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_mobile_notifications()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._sync_mobile_notifications()
        return result

    def unlink(self):
        self._mobile_existing_notifications().action_mark_read()
        return super().unlink()
