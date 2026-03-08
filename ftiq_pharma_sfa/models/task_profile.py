from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


TASK_PROFILE_CODES = [
    ("visit", "Visit"),
    ("order", "Order"),
    ("delivery", "Delivery"),
    ("collection", "Collection"),
    ("stock", "Stock Check"),
    ("report", "Report"),
    ("other", "Other"),
]


class FtiqTaskProfile(models.Model):
    _name = "ftiq.task.profile"
    _description = "Task Profile"
    _order = "sequence, name, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Selection(TASK_PROFILE_CODES, required=True, default="visit")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(translate=True)

    requires_partner = fields.Boolean(default=True)
    requires_associated_partner = fields.Boolean()
    requires_user = fields.Boolean(default=True)
    requires_products = fields.Boolean()
    requires_check_in = fields.Boolean(default=True)
    requires_photos = fields.Boolean()
    required_photo_count = fields.Integer(default=0)
    requires_confirmation = fields.Boolean()
    allow_manual_completion = fields.Boolean(default=False)

    _sql_constraints = [
        ("ftiq_task_profile_name_unique", "unique(name)", "Task profile name must be unique."),
    ]

    @api.constrains("required_photo_count", "requires_photos")
    def _check_required_photo_count(self):
        for rec in self:
            if rec.required_photo_count < 0:
                raise ValidationError(_("Required photo count cannot be negative."))
            if rec.required_photo_count and not rec.requires_photos:
                raise ValidationError(
                    _("A required photo count can only be set when the profile requires photos.")
                )

    @api.model
    def get_default_profile(self, code, fallback_code="other"):
        profile = self.search([("code", "=", code), ("active", "=", True)], order="sequence, id", limit=1)
        if profile or not fallback_code:
            return profile
        return self.search([("code", "=", fallback_code), ("active", "=", True)], order="sequence, id", limit=1)
