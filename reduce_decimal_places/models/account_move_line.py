from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model
    def reduce_decimal_places_by_currency(self):
        """
        Adjust decimal places based on the currency: 
        - IQD (Iraqi Dinar): 0 decimal places
        - USD (US Dollar): 2 decimal places
        """
        _logger.info("Starting to adjust decimal places based on currency...")

        journal_lines = self.search([])  # Get all journal lines
        for line in journal_lines:
            if line.currency_id:
                # Determine decimal places based on currency
                if line.currency_id.name == 'IQD':  # Iraqi Dinar
                    decimal_places = 0
                elif line.currency_id.name == 'USD':  # US Dollar
                    decimal_places = 2
                else:
                    continue  # Skip other currencies

                # Original values
                original_debit = line.debit
                original_credit = line.credit
                original_amount_currency = line.amount_currency

                # Update values with rounded values
                line.debit = round(original_debit, decimal_places)
                line.credit = round(original_credit, decimal_places)
                line.amount_currency = round(original_amount_currency, decimal_places)

                # Log changes (optional)
                _logger.info(
                    "Updated line ID %s: debit %s -> %s, credit %s -> %s, amount_currency %s -> %s (currency: %s)",
                    line.id,
                    original_debit, line.debit,
                    original_credit, line.credit,
                    original_amount_currency, line.amount_currency,
                    line.currency_id.name,
                )

        _logger.info("Finished adjusting decimal places based on currency.")
