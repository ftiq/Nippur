from odoo import _, api, fields, models
from odoo.tools.mail import html2plaintext


class MailActivity(models.Model):
    _inherit = "mail.activity"

    def _mobile_target_record(self):
        self.ensure_one()
        if not self.res_model or not self.res_id:
            return self.env["mail.activity"]
        try:
            return self.env[self.res_model].browse(self.res_id).exists()
        except Exception:
            return self.env["mail.activity"]

    def _mobile_notification_title(self):
        self.ensure_one()
        activity_label = self.activity_type_id.display_name or _("Activity")
        target_name = self.res_name or self._mobile_target_record().display_name or ""
        if target_name:
            return _("%(activity)s: %(record)s") % {
                "activity": activity_label,
                "record": target_name,
            }
        return activity_label

    def _mobile_notification_body(self):
        self.ensure_one()
        parts = []
        summary = (self.summary or "").strip()
        if summary:
            parts.append(summary)
        note = html2plaintext(self.note or "").strip()
        if note and note != summary:
            parts.append(note)
        if self.date_deadline:
            parts.append(_("Due: %s") % fields.Date.to_string(self.date_deadline))
        return "\n".join(parts[:3]) or self._mobile_notification_title()

    def _mobile_notification_payload(self):
        self.ensure_one()
        return {
            "message_type": "activity",
            "activity_id": self.id,
            "activity_type_id": self.activity_type_id.id or "",
            "activity_type_name": self.activity_type_id.display_name or "",
            "activity_state": self.state or "",
            "date_deadline": fields.Date.to_string(self.date_deadline) if self.date_deadline else "",
            "target_model": self.res_model or "",
            "target_id": self.res_id or "",
        }

    def _mark_mobile_notifications_read(self, user_ids=None):
        domain = [
            ("source_model", "=", "mail.activity"),
            ("source_res_id", "in", self.ids),
        ]
        if user_ids:
            domain.append(("user_id", "in", list(user_ids)))
        notifications = self.env["ftiq.mobile.notification"].sudo().search(domain)
        if notifications:
            notifications.action_mark_read()

    def _sync_mobile_notifications(self):
        notification_model = self.env["ftiq.mobile.notification"]
        for activity in self:
            if not activity.active:
                activity._mark_mobile_notifications_read()
                continue
            user = activity.user_id.exists()
            if not user or user.share or not activity.res_model or not activity.res_id:
                continue
            target = activity._mobile_target_record()
            notification_model.create_for_users(
                user,
                title=activity._mobile_notification_title(),
                body=activity._mobile_notification_body(),
                category=notification_model.category_for_model(
                    activity.res_model,
                    default="activity",
                ),
                priority="urgent" if activity.state == "overdue" else "normal",
                target=target,
                source=activity,
                author=self.env.user,
                payload=activity._mobile_notification_payload(),
                event_key=f"mail_activity:{activity.id}",
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_mobile_notifications()
        return records

    def write(self, vals):
        previous_user_ids = {activity.id: activity.user_id.id for activity in self}
        result = super().write(vals)
        if "user_id" in vals:
            for activity in self:
                previous_user_id = previous_user_ids.get(activity.id)
                if previous_user_id and previous_user_id != activity.user_id.id:
                    activity._mark_mobile_notifications_read(user_ids=[previous_user_id])
        self._sync_mobile_notifications()
        return result

    def unlink(self):
        self._mark_mobile_notifications_read()
        return super().unlink()
