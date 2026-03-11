from odoo import fields, models


class FtiqMobileRequestLog(models.Model):
    _name = "ftiq.mobile.request.log"
    _description = "FTIQ Mobile Request Log"
    _order = "create_date desc, id desc"

    request_uid = fields.Char(required=True, copy=False, index=True)
    request_path = fields.Char(required=True, copy=False)
    user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        copy=False,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        copy=False,
        index=True,
    )
    res_model = fields.Char(required=True, copy=False, index=True)
    res_id = fields.Integer(required=True, copy=False, index=True)

    _sql_constraints = [
        (
            "ftiq_mobile_request_uid_user_unique",
            "unique(request_uid, user_id, request_path)",
            "This mobile request has already been processed.",
        ),
    ]
