from odoo import fields, models


class FtiqMobileDevice(models.Model):
    _name = "ftiq.mobile.device"
    _description = "FTIQ Mobile Device"
    _order = "last_seen_at desc, id desc"

    name = fields.Char(required=True, default="Mobile Device")
    installation_id = fields.Char(required=True, index=True)
    user_id = fields.Many2one("res.users", required=True, index=True, ondelete="cascade")
    partner_id = fields.Many2one(
        "res.partner",
        related="user_id.partner_id",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="user_id.company_id",
        store=True,
        readonly=True,
    )
    platform = fields.Char()
    device_name = fields.Char()
    device_model = fields.Char()
    app_version = fields.Char()
    build_number = fields.Char()
    locale = fields.Char()
    notification_enabled = fields.Boolean(default=False)
    location_enabled = fields.Boolean(default=False)
    fcm_token = fields.Char()
    last_seen_at = fields.Datetime(default=fields.Datetime.now)
    last_registration_at = fields.Datetime(default=fields.Datetime.now)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "ftiq_mobile_device_installation_unique",
            "unique(installation_id)",
            "The mobile installation identifier must be unique.",
        ),
    ]
