import logging

from odoo import _, api, models
from odoo.tools import html2plaintext


_logger = logging.getLogger(__name__)


class MailNotification(models.Model):
    _inherit = "mail.notification"

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
        for notification in self.exists():
            if notification._ftiq_skip_mobile_push():
                continue
            payload = notification._ftiq_mobile_payload()
            partner = notification.res_partner_id
            if not partner or not payload["title"]:
                continue
            try:
                Device.push_to_partners(
                    partner,
                    payload["title"],
                    payload["body"],
                    data=payload["data"],
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
        if self.notification_type != "inbox":
            return True
        if (message.model or "").strip() != "project.task" or not message.res_id:
            return True
        if message.author_id and message.author_id == partner:
            return True
        if message.create_uid and message.create_uid.partner_id == partner:
            return True
        if not self._ftiq_is_task_chatter_message(message):
            return True
        return False

    def _ftiq_is_task_chatter_message(self, message):
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
        message = self.mail_message_id
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
