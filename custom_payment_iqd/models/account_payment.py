from odoo import models, fields, api

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    sum_iqd = fields.Float(
        string='IQD Balance',
        compute='_compute_sum_iqd',
        currency_field='currency_id'
    )

    sum_usd = fields.Float(
        string='USD Balance',
        compute='_compute_sum_usd',
        currency_field='currency_id'
    )

    @api.depends('partner_id', 'partner_id.credit', 'partner_id.debit', 'line_ids.custom_amount', 'line_ids.currency_id', 'line_ids.move_id.state')
    def _compute_sum_iqd(self):
        for record in self:
            total = 0.0
            if record.partner_id:
                # Search for all account move lines of this partner in IQD currency
                move_lines = self.env['account.move.line'].search([
                    ('partner_id', '=', record.partner_id.id),
                    ('currency_id.name', '=', 'IQD'),
                    ('account_id.account_type', '=', 'asset_receivable'),
                    ('move_id.state', '=', 'posted')
                ])
                # Sum up the custom amounts for the filtered move lines
                total = sum(line.custom_amount for line in move_lines)
            record.sum_iqd = total

    @api.depends('partner_id', 'partner_id.credit', 'partner_id.debit', 'line_ids.custom_amount', 'line_ids.currency_id', 'line_ids.move_id.state')
    def _compute_sum_usd(self):
        for record in self:
            total = 0.0
            if record.partner_id:
                # Search for all account move lines of this partner in USD currency
                move_lines = self.env['account.move.line'].search([
                    ('partner_id', '=', record.partner_id.id),
                    ('currency_id.name', '=', 'USD'),
                    ('account_id.account_type', '=', 'asset_receivable'),
                    ('move_id.state', '=', 'posted')
                ])
                # Sum up the custom amounts for the filtered move lines
                total = sum(line.custom_amount for line in move_lines)
            record.sum_usd = total


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    sum_iqd = fields.Float(
        string='IQD Balance',
        compute='_compute_sum_iqd',
        currency_field='currency_id'
    )

    sum_usd = fields.Float(
        string='USD Balance',
        compute='_compute_sum_usd',
        currency_field='currency_id'
    )

    @api.depends('partner_id', 'partner_id.credit', 'partner_id.debit', 'order_line.price_unit', 'order_line.currency_id', 'order_line.state')
    def _compute_sum_iqd(self):
        for record in self:
            total = 0.0
            if record.partner_id:
                # Search for all account move lines of this partner in IQD currency
                move_lines = self.env['account.move.line'].search([
                    ('partner_id', '=', record.partner_id.id),
                    ('currency_id.name', '=', 'IQD'),
                    ('account_id.account_type', '=', 'asset_receivable'),
                    ('move_id.state', '=', 'posted')
                ])
                # Sum up the custom amounts for the filtered move lines
                total = sum(line.custom_amount for line in move_lines)
            record.sum_iqd = total

    @api.depends('partner_id', 'partner_id.credit', 'partner_id.debit', 'order_line.price_unit', 'order_line.currency_id', 'order_line.state')
    def _compute_sum_usd(self):
        for record in self:
            total = 0.0
            if record.partner_id:
                # Search for all account move lines of this partner in USD currency
                move_lines = self.env['account.move.line'].search([
                    ('partner_id', '=', record.partner_id.id),
                    ('currency_id.name', '=', 'USD'),
                    ('account_id.account_type', '=', 'asset_receivable'),
                    ('move_id.state', '=', 'posted')
                ])
                # Sum up the custom amounts for the filtered move lines
                total = sum(line.custom_amount for line in move_lines)
            record.sum_usd = total
