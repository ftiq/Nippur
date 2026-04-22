import logging

from odoo import _, api, models
from odoo.tools import html2plaintext


_logger = logging.getLogger(__name__)


class MailMessage(models.Model):
    _inherit = "mail.message"

    _FTIQ_TASK_CHATTER_SUBTYPES = {
        "mail.mt_comment",
        "mail.mt_note",
    }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._queue_ftiq_task_chatter_mobile_push()
        return records

    def _queue_ftiq_task_chatter_mobile_push(self):
        message_ids = self.ids
        if not message_ids:
            return
        registry = self.env.registry
        context = dict(self.env.context)

        def _send_after_commit():
            with registry.cursor() as cr:
                env = api.Environment(cr, self.env.uid, context)
                env["mail.message"].sudo().browse(message_ids)._send_ftiq_task_chatter_mobile_push_now()
                cr.commit()

        postcommit = getattr(self.env.cr, "postcommit", None)
        if postcommit and hasattr(postcommit, "add"):
            postcommit.add(_send_after_commit)
        else:
            _send_after_commit()

    def _ftiq_task_chatter_skip_reason(self):
        self.ensure_one()
        message = self.sudo()
        if (message.model or "").strip() != "project.task" or not message.res_id:
            return "not_task_message"
        if (message.message_type or "") != "comment":
            return f"message_type:{message.message_type or ''}"
        if "tracking_value_ids" in message._fields and message.tracking_value_ids:
            return "tracking_message"
        subtype_xmlid = ""
        if message.subtype_id:
            subtype_xmlid = message.subtype_id.get_external_id().get(message.subtype_id.id, "")
        if subtype_xmlid and subtype_xmlid not in self._FTIQ_TASK_CHATTER_SUBTYPES:
            return f"subtype:{subtype_xmlid}"
        if not html2plaintext(message.body or "").strip():
            return "empty_body"
        return ""

    def _ftiq_task_chatter_title(self):
        self.ensure_one()
        message = self.sudo()
        subject = (message.subject or "").strip()
        if subject:
            return subject
        task_name = (message.record_name or "").strip()
        subtype_xmlid = ""
        if message.subtype_id:
            subtype_xmlid = message.subtype_id.get_external_id().get(message.subtype_id.id, "")
        prefix = _("New note on task") if subtype_xmlid == "mail.mt_note" else _("New message on task")
        return f"{prefix}: {task_name}" if task_name else prefix

    def _ftiq_task_chatter_data(self, task):
        self.ensure_one()
        return {
            "notification_id": "",
            "notification_type": "task_chatter",
            "target_model": "project.task",
            "target_id": str(task.id),
            "target_route": "task",
            "related_client_id": str(task.partner_id.commercial_partner_id.id)
            if task.partner_id
            else "",
            "mail_message_id": str(self.id),
        }

    def _send_ftiq_task_chatter_mobile_push_now(self):
        Device = self.env["ftiq.mobile.device"].sudo()
        Task = self.env["project.task"].sudo()
        for message in self.sudo().exists():
            if (message.model or "").strip() != "project.task":
                continue
            reason = message._ftiq_task_chatter_skip_reason()
            if reason:
                _logger.info(
                    "FTIQ mobile task chatter direct push skipped message=%s task=%s reason=%s",
                    message.id,
                    message.res_id or "",
                    reason,
                )
                continue
            task = Task.browse(message.res_id).exists()
            if not task:
                _logger.info(
                    "FTIQ mobile task chatter direct push skipped message=%s task=%s reason=missing_task",
                    message.id,
                    message.res_id or "",
                )
                continue
            excluded_partner_ids = {
                partner_id
                for partner_id in (
                    message.author_id.id if message.author_id else 0,
                    message.create_uid.partner_id.id if message.create_uid and message.create_uid.partner_id else 0,
                )
                if partner_id
            }
            users = task.user_ids.filtered(lambda user: user.active and not user.share)
            partners = users.mapped("partner_id").exists().filtered(
                lambda partner: partner.id not in excluded_partner_ids
            )
            if not partners:
                _logger.info(
                    "FTIQ mobile task chatter direct push skipped message=%s task=%s reason=no_assignee_recipients users=%s excluded_partners=%s",
                    message.id,
                    task.id,
                    users.ids,
                    sorted(excluded_partner_ids),
                )
                continue
            title = message._ftiq_task_chatter_title()
            body = html2plaintext(message.body or "").strip() or title
            sent = Device.push_to_partners(
                partners,
                title,
                body,
                data=message._ftiq_task_chatter_data(task),
            )
            _logger.info(
                "FTIQ mobile task chatter direct push message=%s task=%s assignee_users=%s recipient_partners=%s sent=%s",
                message.id,
                task.id,
                users.ids,
                partners.ids,
                sent,
            )
