import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


_logger = logging.getLogger(__name__)


class FtiqTeamMessage(models.Model):
    _name = "ftiq.team.message"
    _description = "FTIQ Team Message"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _rec_name = "subject"

    subject = fields.Char(required=True, tracking=True)
    body = fields.Text(required=True)
    message_type = fields.Selection(
        [
            ("note", "Note"),
            ("alert", "Alert"),
        ],
        string="Message Type",
        required=True,
        default="note",
        tracking=True,
    )
    priority = fields.Selection(
        [
            ("normal", "Normal"),
            ("urgent", "Urgent"),
        ],
        default="normal",
        tracking=True,
    )
    author_id = fields.Many2one(
        "res.users",
        string="Author",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
    )
    team_id = fields.Many2one(
        "crm.team",
        string="Team",
        required=True,
        index=True,
        tracking=True,
    )
    target_user_id = fields.Many2one(
        "res.users",
        string="Target Representative",
        tracking=True,
        index=True,
    )
    task_id = fields.Many2one(
        "ftiq.daily.task",
        string="Linked Task",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    is_team_wide = fields.Boolean(
        string="Broadcast To Team",
        default=True,
        tracking=True,
    )

    def _ensure_current_user_can_manage_team(self, team):
        current_user = self.env.user
        if current_user.has_group("ftiq_pharma_sfa.group_ftiq_manager"):
            return
        if (
            not current_user.has_group("ftiq_pharma_sfa.group_ftiq_supervisor")
            or not team
            or team.user_id != current_user
        ):
            raise AccessError(
                _("You can only publish team messages for the teams you supervise.")
            )

    def _validate_payload(self, vals):
        team = self.env["crm.team"].browse(vals.get("team_id"))
        if not team.exists():
            raise ValidationError(_("A valid team is required."))
        self._ensure_current_user_can_manage_team(team)

        target_user = self.env["res.users"].browse(vals.get("target_user_id"))
        if target_user and target_user not in team.member_ids:
            raise ValidationError(_("The selected representative is not a member of this team."))

        task = self.env["ftiq.daily.task"].browse(vals.get("task_id"))
        if task and task.user_id not in (team.member_ids | team.user_id):
            raise ValidationError(_("The linked task does not belong to the selected team."))

    def _recipient_partners(self):
        self.ensure_one()
        recipients = self.env["res.partner"]
        if self.target_user_id:
            recipients |= self.target_user_id.partner_id
            recipients |= self.team_id.user_id.partner_id
        else:
            recipients |= self.team_id.member_ids.mapped("partner_id")
            recipients |= self.team_id.user_id.partner_id
        return (recipients - self.author_id.partner_id).filtered(lambda partner: partner)

    def _push_recipient_users(self):
        self.ensure_one()
        if self.target_user_id:
            recipients = self.target_user_id | self.team_id.user_id
        else:
            recipients = self.team_id.member_ids | self.team_id.user_id
        return (recipients - self.author_id).filtered(
            lambda user: not user.share and user.company_id == self.company_id
        )

    def _post_initial_chatter_message(self):
        for record in self:
            recipients = record._recipient_partners()
            if recipients:
                record.message_subscribe(partner_ids=recipients.ids)
            record.message_post(
                subject=record.subject,
                body=record.body,
                partner_ids=recipients.ids,
                subtype_xmlid="mail.mt_note",
            )

    def _dispatch_push_notifications(self):
        push_service = self.env["ftiq.firebase.push.service"]
        for record in self:
            try:
                push_service.send_team_message_push(record)
            except Exception:
                _logger.exception(
                    "FTIQ team message push delivery failed for message %s",
                    record.id,
                )

    @api.model_create_multi
    def create(self, vals_list):
        current_user = self.env.user
        for vals in vals_list:
            if not vals.get("team_id") and current_user.sale_team_id:
                vals["team_id"] = current_user.sale_team_id.id
            if "is_team_wide" not in vals:
                vals["is_team_wide"] = not bool(vals.get("target_user_id"))
            if vals.get("target_user_id"):
                vals["is_team_wide"] = False
            vals["author_id"] = current_user.id
            vals.setdefault("company_id", current_user.company_id.id)
            self._validate_payload(vals)
        records = super().create(vals_list)
        records._post_initial_chatter_message()
        records._dispatch_push_notifications()
        return records
