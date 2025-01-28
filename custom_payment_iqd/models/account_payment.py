from odoo import models, fields, api

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    sum_iqd = fields.Float(
        string='IQD Balance',
        compute='_compute_sum_iqd'
    )

    sum_usd = fields.Float(
        string='USD Balance',
        compute='_compute_sum_usd'
    )

    @api.depends('partner_id', 'move_id.line_ids.custom_amount', 'move_id.line_ids.currency_id', 'move_id.line_ids.move_id.state')
    def _compute_sum_iqd(self):
        for record in self:
            total = 0.0
            if record.partner_id and record.move_id:
                move_lines = record.move_id.line_ids.filtered(lambda l:
                    l.currency_id.name == 'IQD' and
                    l.account_id.account_type == 'asset_receivable' and
                    l.move_id.state == 'posted'
                )
                total = sum(line.custom_amount for line in move_lines)
            record.sum_iqd = total

    @api.depends('partner_id', 'move_id.line_ids.custom_amount', 'move_id.line_ids.currency_id', 'move_id.line_ids.move_id.state')
    def _compute_sum_usd(self):
        for record in self:
            total = 0.0
            if record.partner_id and record.move_id:
                move_lines = record.move_id.line_ids.filtered(lambda l:
                    l.currency_id.name == 'USD' and
                    l.account_id.account_type == 'asset_receivable' and
                    l.move_id.state == 'posted'
                )
                total = sum(line.custom_amount for line in move_lines)
            record.sum_usd = total
