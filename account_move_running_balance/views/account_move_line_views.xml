from psycopg2 import sql
from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    running_balance = fields.Monetary(
        string="Running Balance",
        store=False,
        compute="_compute_running_balance",
        currency_field="company_currency_id",
        help="Running balance in company currency.",
    )
    running_balance_currency = fields.Monetary(
        string="Running Balance in Currency",
        store=False,
        compute="_compute_running_balance",
        currency_field="currency_id",
        help="Running balance in transaction currency.",
    )

    @api.depends("debit", "credit", "amount_currency")
    def _compute_running_balance(self):
        for record in self:
            query = """
                SELECT SUM(debit - credit), SUM(amount_currency)
                FROM account_move_line
                WHERE account_id = %s
                  AND company_id = %s
                  AND (date < %s OR (date = %s AND id <= %s))
            """
            args = [
                record.account_id.id,
                record.company_id.id,
                record.date,
                record.date,
                record.id,
            ]

            # إذا الحساب من نوع Receivable/Payable نضيف شرط الشريك
            if record.account_id.account_type in ("asset_receivable", "liability_payable"):
                query += " AND partner_id = %s"
                args.append(record.partner_id.id or None)

            # لو في عملة نضيف شرطها
            if record.currency_id:
                query += " AND currency_id = %s"
                args.append(record.currency_id.id)

            self.env.cr.execute(query, tuple(args))
            result = self.env.cr.fetchone()
            record.running_balance = result[0] or 0.0
            record.running_balance_currency = result[1] or 0.0
