from odoo import _, api, fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    ftiq_plan_ids = fields.One2many('ftiq.weekly.plan', 'project_id', string='FTIQ Plans')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._notify_mobile_project_membership()
        return records

    def write(self, vals):
        old_manager_ids = {record.id: record.user_id.id for record in self}
        old_member_ids = {
            record.id: set(record.favorite_user_ids.ids)
            for record in self
        }
        result = super().write(vals)
        if any(field_name in vals for field_name in ('user_id', 'favorite_user_ids')):
            self._notify_mobile_project_membership(
                old_manager_ids=old_manager_ids,
                old_member_ids=old_member_ids,
            )
        return result

    def _project_notification_users(self):
        self.ensure_one()
        users = (self.favorite_user_ids | self.user_id).filtered(
            lambda user: not user.share and user.active
        )
        return (users - self.env.user).filtered(
            lambda user: user.company_id == self.company_id
        )

    def _notify_mobile_project_membership(self, old_manager_ids=None, old_member_ids=None):
        for record in self:
            previous_ids = set()
            if old_manager_ids is not None:
                previous_manager_id = old_manager_ids.get(record.id)
                if previous_manager_id:
                    previous_ids.add(previous_manager_id)
            if old_member_ids is not None:
                previous_ids |= set(old_member_ids.get(record.id, set()))
            recipients = record._project_notification_users()
            if previous_ids:
                recipients = recipients.filtered(lambda user: user.id not in previous_ids)
            if not recipients:
                continue
            body = _(
                'You were added to project %s.'
            ) % (record.display_name,)
            record.message_post(
                subject=_('Project assignment'),
                body=body,
                partner_ids=recipients.mapped('partner_id').ids,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )


class ProjectTask(models.Model):
    _inherit = 'project.task'

    ftiq_plan_id = fields.Many2one('ftiq.weekly.plan', string='FTIQ Weekly Plan', ondelete='set null', index=True)
    ftiq_plan_line_id = fields.Many2one('ftiq.weekly.plan.line', string='FTIQ Plan Line', ondelete='set null', index=True)
    ftiq_daily_task_id = fields.Many2one('ftiq.daily.task', string='FTIQ Daily Task', ondelete='set null', index=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._notify_mobile_task_assignment()
        return records

    def write(self, vals):
        old_assignee_ids = {
            record.id: set(record.user_ids.ids)
            for record in self
        }
        old_stage_ids = {
            record.id: record.stage_id.id
            for record in self
        }
        old_closed_state = {
            record.id: bool(record.is_closed)
            for record in self
        }
        result = super().write(vals)
        if 'user_ids' in vals:
            self._notify_mobile_task_assignment(old_assignee_ids=old_assignee_ids)
        if any(field_name in vals for field_name in ('stage_id', 'state')):
            self._notify_mobile_task_progress(
                old_stage_ids=old_stage_ids,
                old_closed_state=old_closed_state,
            )
        return result

    def _task_notification_users(self):
        self.ensure_one()
        users = (self.user_ids | self.project_id.user_id).filtered(
            lambda user: not user.share and user.active
        )
        return (users - self.env.user).filtered(
            lambda user: user.company_id == self.company_id
        )

    def _notify_mobile_task_assignment(self, old_assignee_ids=None):
        for record in self:
            recipients = record._task_notification_users()
            if old_assignee_ids is None:
                recipients = recipients.filtered(lambda user: user.id in set(record.user_ids.ids))
            else:
                previous_ids = set(old_assignee_ids.get(record.id, set()))
                recipients = recipients.filtered(
                    lambda user: user.id in set(record.user_ids.ids) and user.id not in previous_ids
                )
            if not recipients:
                continue
            body = _(
                'You were assigned to task %s.'
            ) % (record.display_name,)
            if record.project_id:
                body = _(
                    'You were assigned to task %s in project %s.'
                ) % (record.display_name, record.project_id.display_name)
            record.message_post(
                subject=_('Task assignment'),
                body=body,
                partner_ids=recipients.mapped('partner_id').ids,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )

    def _notify_mobile_task_progress(self, old_stage_ids=None, old_closed_state=None):
        for record in self:
            previous_stage_id = old_stage_ids.get(record.id) if old_stage_ids else False
            previous_closed = old_closed_state.get(record.id) if old_closed_state else False
            if previous_stage_id == record.stage_id.id and previous_closed == bool(record.is_closed):
                continue
            recipients = record._task_notification_users()
            if not recipients:
                continue
            if record.is_closed and not previous_closed:
                subject = _('Task completed')
                body = _(
                    'Task %s was completed.'
                ) % (record.display_name,)
            else:
                stage_name = record.stage_id.display_name or _('Updated')
                subject = _('Task updated')
                body = _(
                    'Task %s moved to %s.'
                ) % (record.display_name, stage_name)
            record.message_post(
                subject=subject,
                body=body,
                partner_ids=recipients.mapped('partner_id').ids,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
