from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class FtiqCollectionDraft(models.Model):
    _name = "ftiq.collection.draft"
    _description = "Mobile Collection Draft"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(default=lambda self: _("New"), copy=False, readonly=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        index=True,
        tracking=True,
    )
    commercial_partner_id = fields.Many2one(
        "res.partner",
        string="Commercial Customer",
        related="partner_id.commercial_partner_id",
        store=True,
        index=True,
    )
    collector_id = fields.Many2one(
        "res.users",
        string="Collector",
        default=lambda self: self.env.user,
        required=True,
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    invoice_ids = fields.Many2many(
        "account.move",
        "ftiq_collection_draft_account_move_rel",
        "draft_id",
        "move_id",
        string="Open Invoices",
        domain=[
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
        ],
        tracking=True,
    )
    amount = fields.Monetary(required=True, tracking=True)
    open_invoice_residual = fields.Monetary(
        string="Selected Invoice Residual",
        compute="_compute_open_invoice_residual",
        store=True,
    )
    payment_note = fields.Text(string="Payment Note")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    mobile_request_uid = fields.Char(copy=False, index=True)
    submitted_at = fields.Datetime(copy=False, readonly=True)
    rejected_at = fields.Datetime(copy=False, readonly=True)
    rejected_by_id = fields.Many2one("res.users", copy=False, readonly=True)
    rejection_reason = fields.Text(copy=False)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "ftiq_collection_draft_ir_attachment_rel",
        "draft_id",
        "attachment_id",
        string="Attachments",
        copy=False,
    )
    attachment_count = fields.Integer(compute="_compute_attachment_count")

    ftiq_mobile_latitude = fields.Float(copy=False)
    ftiq_mobile_longitude = fields.Float(copy=False)
    ftiq_mobile_accuracy = fields.Float(copy=False)
    ftiq_mobile_is_mock = fields.Boolean(copy=False)
    ftiq_mobile_location_at = fields.Datetime(copy=False)

    _sql_constraints = [
        (
            "mobile_request_uid_unique",
            "unique(mobile_request_uid)",
            "This mobile collection request was already submitted.",
        ),
    ]

    @api.depends("invoice_ids.amount_residual", "invoice_ids.currency_id")
    def _compute_open_invoice_residual(self):
        for draft in self:
            draft.open_invoice_residual = sum(draft.invoice_ids.mapped("amount_residual"))

    @api.depends("attachment_ids")
    def _compute_attachment_count(self):
        for draft in self:
            draft.attachment_count = len(draft.attachment_ids)

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = sequence.next_by_code("ftiq.collection.draft") or _("New")
            if not vals.get("submitted_at") and vals.get("state") == "submitted":
                vals["submitted_at"] = fields.Datetime.now()
        return super().create(vals_list)

    @api.constrains("amount", "invoice_ids", "state")
    def _check_collection_amount(self):
        for draft in self:
            if draft.amount <= 0:
                raise ValidationError(_("Collection amount must be greater than zero."))
            if draft.state == "submitted" and not draft.invoice_ids:
                raise ValidationError(_("Select at least one open invoice."))
            if draft.invoice_ids and draft.amount > draft.open_invoice_residual + 0.0001:
                raise ValidationError(
                    _("Collection amount cannot exceed the selected open invoice residual.")
                )

    def action_submit(self):
        for draft in self:
            if draft.state != "draft":
                continue
            if not draft.invoice_ids:
                raise ValidationError(_("Select at least one open invoice before submitting."))
            draft.write({"state": "submitted", "submitted_at": fields.Datetime.now()})

    def action_reject(self):
        if not self.env.user.has_group("account.group_account_invoice"):
            raise AccessError(_("Only accounting users can reject collection drafts."))
        self.write(
            {
                "state": "rejected",
                "rejected_at": fields.Datetime.now(),
                "rejected_by_id": self.env.user.id,
            }
        )

    def action_cancel(self):
        self.filtered(lambda draft: draft.state in ("draft", "submitted")).write(
            {"state": "cancelled"}
        )
