from odoo import models, fields


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    is_field_expense = fields.Boolean(string='Field Expense', default=False)
    ftiq_attendance_id = fields.Many2one('ftiq.field.attendance', string='Attendance', copy=False)
    ftiq_expense_type = fields.Selection([
        ('transport', 'Transportation'),
        ('fuel', 'Fuel'),
        ('food', 'Food & Meals'),
        ('accommodation', 'Accommodation'),
        ('phone', 'Phone & Communication'),
        ('parking', 'Parking'),
        ('other', 'Other'),
    ], string='Field Expense Type')
