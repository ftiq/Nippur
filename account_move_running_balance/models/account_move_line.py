from psycopg2 import sql
from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    running_balance = fields.Monetary(
        string="Running Balance",
        store=False,
        compute="_compute_running_balance",
        currency_field="currency_id",
        help="Running balance based on account, partner, and currency.",
    )
    running_balance_currency = fields.Monetary(
        string="Running Balance in Currency",
        store=False,
        compute="_compute_running_balance",
        currency_field="currency_id",
        help="Running balance in currency for the selected account, partner, and currency.",
    )

    @api.depends_context("domain_running_balance")
    def _compute_running_balance(self):
        """
        Compute running balance for each combination of:
        - `account_id` and `currency_id` for normal accounts.
        - `account_id`, `currency_id`, and `partner_id` for "Receivable" or "Payable" accounts.
        """
        query_base = """
            SELECT SUM(balance), SUM(amount_currency)
            FROM account_move_line
            WHERE {}
                AND account_id = %s
                AND company_id = %s
                AND (date < %s OR (date = %s AND id <= %s))
        """

        # Filter only for Receivable or Payable accounts
        receivable_payable_filter = """
            AND account_id IN (
                SELECT id FROM account_account
                WHERE account_type IN ('asset_receivable', 'liability_payable')
            )
        """

        for record in self:
            record.running_balance = 0.0
            record.running_balance_currency = 0.0

            # Build WHERE clause dynamically from context
            query = self._where_calc(self.env.context.get("domain_running_balance", []))
            _, where_clause, where_params = query.get_sql()

            # Base query adjustments
            query_full = sql.SQL(query_base).format(sql.SQL(where_clause or "TRUE"))
            query_args = where_params + [
                record.account_id.id,
                record.company_id.id,
                record.date,
                record.date,
                record.id,
            ]

            # Check if account type is Receivable or Payable
            if record.account_id.account_type in ("asset_receivable", "liability_payable"):
                query_full += sql.SQL(receivable_payable_filter)
                # Add filtering for partner_id
                if record.partner_id:
                    query_full += sql.SQL(" AND partner_id = %s")
                    query_args.append(record.partner_id.id)

            # Add currency-specific filtering
            if record.currency_id:
                query_full += sql.SQL(" AND currency_id = %s")
                query_args.append(record.currency_id.id)

            # Execute the query and fetch results
            self.env.cr.execute(query_full, tuple(query_args))
            result = self.env.cr.fetchone()
            if result:
                record.running_balance = result[0] or 0.0
                record.running_balance_currency = result[1] or 0.0
