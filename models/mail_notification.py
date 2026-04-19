import logging

from odoo import api, models
from odoo.tools import html2plaintext


_logger = logging.getLogger(__name__)


class MailNotification(models.Model):
    _inherit = "mail.notification"

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

    def _ftiq_mobile_payload(self):
        self.ensure_one()
        message = self.mail_message_id
        title = (
            (message.subject or "").strip()
            or (message.record_name or "").strip()
            or "Notification"
        )
        body = html2plaintext(message.body or "").strip() if message else ""
        if not body:
            body = title
        data = {
            "notification_id": str(self.id),
            "target_model": "",
            "target_id": "",
            "target_route": "",
            "related_client_id": "",
        }
        if message:
            data.update(self._ftiq_notification_target_data(message))
        return {
            "title": title,
            "body": body,
            "data": data,
        }

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

        return {
            "target_model": target_model,
            "target_id": target_id,
            "target_route": target_route,
            "related_client_id": related_client_id,
        }
