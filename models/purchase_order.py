from odoo import _, api, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._notify_mobile_purchase_assignment()
        return records

    def write(self, vals):
        old_buyer_ids = {record.id: record.user_id.id for record in self}
        result = super().write(vals)
        if 'user_id' in vals:
            self._notify_mobile_purchase_assignment(old_buyer_ids=old_buyer_ids)
        return result

    def button_confirm(self):
        result = super().button_confirm()
        self._notify_mobile_purchase_event('confirmed')
        return result

    def button_approve(self, force=False):
        result = super().button_approve(force=force)
        self._notify_mobile_purchase_event('approved')
        return result

    def button_cancel(self):
        result = super().button_cancel()
        self._notify_mobile_purchase_event('canceled')
        return result

    def _purchase_notification_users(self):
        self.ensure_one()
        manager_group = self.env.ref(
            'ftiq_pharma_sfa.group_ftiq_manager',
            raise_if_not_found=False,
        )
        users = (self.user_id | self.create_uid).filtered(
            lambda user: not user.share and user.active
        )
        if manager_group:
            users |= manager_group.users.filtered(
                lambda user: not user.share and user.active
            )
        return (users - self.env.user).filtered(
            lambda user: user.company_id == self.company_id
        )

    def _notify_mobile_purchase_assignment(self, old_buyer_ids=None):
        for record in self.filtered('user_id'):
            recipients = record._purchase_notification_users().filtered(
                lambda user: user.id == record.user_id.id
            )
            if old_buyer_ids is not None and old_buyer_ids.get(record.id) == record.user_id.id:
                recipients = self.env['res.users']
            if not recipients:
                continue
            record.message_post(
                subject=_('Purchase assignment'),
                body=_(
                    'You were assigned to purchase order %s.'
                ) % (record.display_name,),
                partner_ids=recipients.mapped('partner_id').ids,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )

    def _notify_mobile_purchase_event(self, event_name):
        event_messages = {
            'confirmed': (
                _('Purchase order confirmed'),
                _('Purchase order %s was confirmed.'),
            ),
            'approved': (
                _('Purchase order approved'),
                _('Purchase order %s was approved.'),
            ),
            'canceled': (
                _('Purchase order canceled'),
                _('Purchase order %s was canceled.'),
            ),
        }
        subject, body_template = event_messages.get(
            event_name,
            (
                _('Purchase order updated'),
                _('Purchase order %s was updated.'),
            ),
        )
        for record in self:
            recipients = record._purchase_notification_users()
            if not recipients:
                continue
            record.message_post(
                subject=subject,
                body=body_template % (record.display_name,),
                partner_ids=recipients.mapped('partner_id').ids,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
