from odoo import api, fields, models

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    remaining_due = fields.Monetary(
        string='Remaining Due',
        currency_field='currency_id',
        compute='_compute_remaining_due',
        store=True
    )

    @api.depends('move_id.line_ids.amount_residual')
    def _compute_remaining_due(self):
        # معالجة السطور على حسب القيد المحاسبي
        moves = self.mapped('move_id')
        for move in moves:
            # نختار سطر الزبون فقط (اللي كوده 121)
            customer_lines = move.line_ids.filtered(lambda l: l.account_id.code == '121')
            # كل السطور الأخرى اللي مو زبون
            target_lines = move.line_ids.filtered(lambda l: l.account_id.code != '121')

            # إذا ما فيه سطر زبون أو سطور أخرى، نحط المتبقي صفر للجميع
            if not customer_lines or not target_lines:
                for line in move.line_ids:
                    line.remaining_due = 0.0
                continue

            # نأخذ المتبقي من الزبون
            residual = customer_lines[0].amount_residual
            # مجموع أرصدة السطور غير الزبون (نستخدم القيمة المطلقة)
            total_amount = sum(abs(l.balance) for l in target_lines)

            for line in move.line_ids:
                if line.account_id.code == '121':
                    line.remaining_due = 0.0
                else:
                    # توزيع المتبقي على حسب نسبة كل سطر
                    line.remaining_due = (
                        (abs(line.balance) / total_amount) * residual
                        if total_amount else 0.0
                    )

                    # ✅ إذا كان اسم السطر "رصيد أفتتاحي"، نعيّن الدائن مساوي للمتبقي
                    if line.name == 'رصيد أفتتاحي':
                        line.credit = line.remaining_due
