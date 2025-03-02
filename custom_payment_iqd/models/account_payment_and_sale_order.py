from odoo import models, fields, api

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    sum_iqd = fields.Float(
        string='IQD Balance',
        compute='_compute_sum_iqd',
        store=False
    )

    sum_usd = fields.Float(
        string='USD Balance',
        compute='_compute_sum_usd',
        store=False
    )

    @api.depends('partner_id')
    def _compute_sum_iqd(self):
        for record in self:
            total = 0.0
            if record.partner_id:
                move_lines = self.env['account.move.line'].search([
                    ('partner_id', '=', record.partner_id.id),
                    ('currency_id.name', '=', 'IQD'),
                    ('account_id.account_type', '=', 'asset_receivable'),
                    ('move_id.state', '=', 'posted')
                ])
                total = sum(line.amount_currency for line in move_lines)
            record.sum_iqd = total

    @api.depends('partner_id')
    def _compute_sum_usd(self):
        for record in self:
            total = 0.0
            if record.partner_id:
                move_lines = self.env['account.move.line'].search([
                    ('partner_id', '=', record.partner_id.id),
                    ('currency_id.name', '=', 'USD'),
                    ('account_id.account_type', '=', 'asset_receivable'),
                    ('move_id.state', '=', 'posted')
                ])
                total = sum(line.amount_currency for line in move_lines)
            record.sum_usd = total


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    sum_iqd = fields.Float(
        string='IQD Balance',
        compute='_compute_sum_iqd',
        store=False
    )

    sum_usd = fields.Float(
        string='USD Balance',
        compute='_compute_sum_usd',
        store=False
    )

    @api.depends('partner_id')
    def _compute_sum_iqd(self):
        for record in self:
            total = 0.0
            if record.partner_id:
                move_lines = self.env['account.move.line'].search([
                    ('partner_id', '=', record.partner_id.id),
                    ('currency_id.name', '=', 'IQD'),
                    ('account_id.account_type', '=', 'asset_receivable'),
                    ('move_id.state', '=', 'posted')
                ])
                total = sum(line.amount_currency for line in move_lines)
            record.sum_iqd = total

    @api.depends('partner_id')
    def _compute_sum_usd(self):
        for record in self:
            total = 0.0
            if record.partner_id:
                move_lines = self.env['account.move.line'].search([
                    ('partner_id', '=', record.partner_id.id),
                    ('currency_id.name', '=', 'USD'),
                    ('account_id.account_type', '=', 'asset_receivable'),
                    ('move_id.state', '=', 'posted')
                ])
                total = sum(line.amount_currency for line in move_lines)
            record.sum_usd = total
