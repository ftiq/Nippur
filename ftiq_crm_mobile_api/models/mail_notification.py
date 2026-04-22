import logging

from odoo import _, api, models
from odoo.tools import html2plaintext


_logger = logging.getLogger(__name__)


class MailNotification(models.Model):
    _inherit = "mail.notification"

    _FTIQ_PUSH_NOTIFICATION_TYPES = {"inbox", "email"}
    _FTIQ_TASK_CHATTER_SUBTYPES = {
        "mail.mt_comment",
        "mail.mt_note",
    }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._queue_mobile_push()
        return records

    def _queue_mobile_push(self):
        notification_ids = self.ids
        if not notification_ids:
            return
        registry = self.env.registry
        dbname = self.env.cr.dbname
        context = dict(self.env.context)

        def _send_after_commit():
            with registry.cursor() as cr:
                env = api.Environment(cr, self.env.uid, context)
                env["mail.notification"].sudo().browse(notification_ids)._send_mobile_push_now()
                cr.commit()

        postcommit = getattr(self.env.cr, "postcommit", None)
        if postcommit and hasattr(postcommit, "add"):
            postcommit.add(_send_after_commit)
        else:
            _send_after_commit()

    def _send_mobile_push_now(self):
        Device = self.env["ftiq.mobile.device"].sudo()
        pushed_message_ids = set()
        for notification in self.exists():
            if notification._ftiq_skip_mobile_push():
                continue
            payload = notification._ftiq_mobile_payload()
            partner = notification.res_partner_id
            if not partner or not payload["title"]:
                continue

            message = notification.mail_message_id.sudo()
            if message.id and message.id not in pushed_message_ids:
                notification._ftiq_send_task_assignee_push(payload)
                pushed_message_ids.add(message.id)

            if (message.model or "").strip() == "project.task":
                _logger.info(
                    "FTIQ mobile task chatter mail.notification recipient push skipped notification=%s partner=%s task=%s type=%s reason=assignee_push_is_authoritative",
                    notification.id,
                    partner.id,
                    message.res_id or "",
                    notification.notification_type or "",
                )
                continue
            try:
                sent = Device.push_to_partners(
                    partner,
                    payload["title"],
                    payload["body"],
                    data=payload["data"],
                )
                _logger.info(
                    "FTIQ mobile task chatter push notification=%s partner=%s sent=%s target=%s:%s type=%s",
                    notification.id,
                    partner.id,
                    sent,
                    payload["data"].get("target_model", ""),
                    payload["data"].get("target_id", ""),
                    notification.notification_type or "",
                )
            except Exception:
                _logger.exception(
                    "Failed to send mobile push for mail.notification %s",
                    notification.id,
                )

    def _ftiq_skip_mobile_push(self):
        self.ensure_one()
        message = self.mail_message_id
        partner = self.res_partner_id
        if not message or not partner:
            return True
        if (self.notification_type or "") not in self._FTIQ_PUSH_NOTIFICATION_TYPES:
            return True
        message_sudo = message.sudo()
        if (message_sudo.model or "").strip() != "project.task" or not message_sudo.res_id:
            return True
        if message_sudo.author_id and message_sudo.author_id.id == partner.id:
            return True
        if message_sudo.create_uid and message_sudo.create_uid.partner_id.id == partner.id:
            return True
        if not self._ftiq_is_task_chatter_message(message_sudo):
            return True
        return False

    def _ftiq_recipient_is_task_assignee(self):
        self.ensure_one()
        message = self.mail_message_id.sudo()
        partner = self.res_partner_id
        if not partner or (message.model or "").strip() != "project.task" or not message.res_id:
            return False
        task = self.env["project.task"].sudo().browse(message.res_id).exists()
        if not task:
            return False
        return partner.id in task.user_ids.mapped("partner_id").ids

    def _ftiq_send_task_assignee_push(self, payload):
        self.ensure_one()
        message = self.mail_message_id.sudo()
        if (message.model or "").strip() != "project.task" or not message.res_id:
            return 0
        task = self.env["project.task"].sudo().browse(message.res_id).exists()
        if not task:
            _logger.info(
                "FTIQ mobile task chatter assignee push skipped notification=%s message=%s task=%s reason=missing_task",
                self.id,
                message.id,
                message.res_id or "",
            )
            return 0
        excluded_partner_ids = {
            partner_id
            for partner_id in (
                message.author_id.id if message.author_id else 0,
                message.create_uid.partner_id.id
                if message.create_uid and message.create_uid.partner_id
                else 0,
            )
            if partner_id
        }
        users = task.user_ids.filtered(lambda user: user.active and not user.share)
        partners = users.mapped("partner_id").exists().filtered(
            lambda partner: partner.id not in excluded_partner_ids
        )
        if not partners:
            _logger.info(
                "FTIQ mobile task chatter assignee push skipped notification=%s message=%s task=%s reason=no_assignee_recipients assignee_users=%s excluded_partners=%s",
                self.id,
                message.id,
                task.id,
                users.ids,
                sorted(excluded_partner_ids),
            )
            return 0
        sent = self.env["ftiq.mobile.device"].sudo().push_to_partners(
            partners,
            payload["title"],
            payload["body"],
            data=payload["data"],
        )
        _logger.info(
            "FTIQ mobile task chatter assignee push notification=%s message=%s task=%s assignee_users=%s recipient_partners=%s sent=%s",
            self.id,
            message.id,
            task.id,
            users.ids,
            partners.ids,
            sent,
        )
        return sent

    def _ftiq_is_task_chatter_message(self, message):
        message = message.sudo()
        if not message or (message.message_type or "") != "comment":
            return False
        if "tracking_value_ids" in message._fields and message.tracking_value_ids:
            return False
        subtype = message.subtype_id
        if subtype:
            xmlid = subtype.get_external_id().get(subtype.id, "")
            if xmlid:
                return xmlid in self._FTIQ_TASK_CHATTER_SUBTYPES
        return bool(html2plaintext(message.body or "").strip())

    def _ftiq_target_record(self, message):
        model_name = (message.model or "").strip()
        if not model_name or not message.res_id:
            return self.env["ir.model"]
        try:
            return self.env[model_name].sudo().browse(message.res_id).exists()
        except KeyError:
            return self.env["ir.model"]

    def _ftiq_mobile_payload(self):
        self.ensure_one()
        message = self.mail_message_id.sudo()
        title = self._ftiq_mobile_title(message)
        body = html2plaintext(message.body or "").strip() if message else ""
        if not body:
            body = title
        data = {
            "notification_id": str(self.id),
            "notification_type": "task_chatter",
            "target_model": "",
            "target_id": "",
            "target_route": "",
            "related_client_id": "",
            "mail_message_id": str(message.id if message else ""),
        }
        if message:
            data.update(self._ftiq_notification_target_data(message))
        return {
            "title": title,
            "body": body,
            "data": data,
        }

    def _ftiq_mobile_title(self, message):
        if not message:
            return "Notification"
        message = message.sudo()
        subject = (message.subject or "").strip()
        if subject:
            return subject
        task_name = (message.record_name or "").strip()
        subtype_xmlid = ""
        if message.subtype_id:
            subtype_xmlid = message.subtype_id.get_external_id().get(message.subtype_id.id, "")
        if subtype_xmlid == "mail.mt_note":
            prefix = _("New note on task")
        else:
            prefix = _("New message on task")
        return f"{prefix}: {task_name}" if task_name else prefix

    def _ftiq_notification_target_data(self, message):
        self.ensure_one()
        message = message.sudo()
        target_model = (message.model or "").strip()
        target_id = str(message.res_id or "")
        target_route = ""
        related_client_id = ""

        if target_model == "project.task" and message.res_id:
            target_route = "task"
            task = self.env["project.task"].sudo().browse(message.res_id).exists()
            if task and "partner_id" in task._fields and task.partner_id:
                related_client_id = str(task.partner_id.commercial_partner_id.id)
        elif target_model == "crm.lead" and message.res_id:
            lead = self.env["crm.lead"].sudo().browse(message.res_id).exists()
            if lead:
                target_route = "deal" if lead.type == "opportunity" else "lead"
                if lead.partner_id:
                    related_client_id = str(lead.partner_id.commercial_partner_id.id)
        elif target_model == "res.partner" and message.res_id:
            target_route = "client"
        elif target_model == "account.move" and message.res_id:
            target_route = "invoice"
            move = self.env["account.move"].sudo().browse(message.res_id).exists()
            if move and move.partner_id:
                related_client_id = str(move.partner_id.commercial_partner_id.id)
        elif target_model == "sale.order" and message.res_id:
            target_route = "sale_order"
            order = self.env["sale.order"].sudo().browse(message.res_id).exists()
            if order and order.partner_id:
                related_client_id = str(order.partner_id.commercial_partner_id.id)

        return {
            "target_model": target_model,
            "target_id": target_id,
            "target_route": target_route,
            "related_client_id": related_client_id,
        }
