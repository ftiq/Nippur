from odoo import _, api, fields, models, Command
from odoo.exceptions import UserError, ValidationError


FTIQ_PAYMENT_POSTED_STATES = ('in_process', 'paid')
FTIQ_RECONCILABLE_ACCOUNT_TYPES = ('asset_receivable', 'liability_payable')


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_field_collection = fields.Boolean(string='Field Collection', default=False, tracking=True)
    ftiq_user_id = fields.Many2one(
        'res.users',
        string='Representative',
        default=lambda self: self.env.uid,
        copy=False,
        tracking=True,
        index=True,
    )
    ftiq_team_id = fields.Many2one('crm.team', string='Sales Team', compute='_compute_ftiq_team_id', store=True, readonly=True)
    ftiq_visit_id = fields.Many2one('ftiq.visit', string='Related Visit', copy=False)
    ftiq_attendance_id = fields.Many2one('ftiq.field.attendance', string='Attendance', copy=False)
    ftiq_daily_task_id = fields.Many2one('ftiq.daily.task', string='Daily Task', copy=False)
    ftiq_partner_area_id = fields.Many2one(related='partner_id.ftiq_area_id', store=True)
    ftiq_latitude = fields.Float(string='Latitude', digits=(10, 7))
    ftiq_longitude = fields.Float(string='Longitude', digits=(10, 7))
    ftiq_check_number = fields.Char(string='Check Number')
    ftiq_check_date = fields.Date(string='Check Date')
    ftiq_bank_name = fields.Char(string='Bank Name')
    ftiq_receipt_image = fields.Binary(string='Receipt Image', attachment=True)
    ftiq_receipt_image_name = fields.Char(string='Receipt Image Name')
    ftiq_collection_line_ids = fields.One2many(
        'ftiq.collection.line',
        'payment_id',
        string='Invoice Allocations',
        copy=False,
    )
    ftiq_allocated_amount = fields.Monetary(
        string='Allocated Amount',
        currency_field='currency_id',
        compute='_compute_ftiq_collection_metrics',
    )
    ftiq_unallocated_amount = fields.Monetary(
        string='Unallocated Amount',
        currency_field='currency_id',
        compute='_compute_ftiq_collection_metrics',
    )
    ftiq_open_invoice_count = fields.Integer(
        string='Open Invoices',
        compute='_compute_ftiq_collection_metrics',
    )
    ftiq_collection_state = fields.Selection([
        ('draft', 'Draft'),
        ('collected', 'Collected'),
        ('deposited', 'Deposited'),
        ('verified', 'Verified'),
    ], string='Collection Status', default='draft', tracking=True)

    @api.depends('ftiq_visit_id.team_id', 'ftiq_user_id.sale_team_id')
    def _compute_ftiq_team_id(self):
        for rec in self:
            rec.ftiq_team_id = rec.ftiq_visit_id.team_id or rec.ftiq_user_id.sale_team_id

    @api.depends('amount', 'partner_id', 'is_field_collection', 'ftiq_collection_line_ids.allocated_amount')
    def _compute_ftiq_collection_metrics(self):
        for rec in self:
            allocated = sum(rec.ftiq_collection_line_ids.mapped('allocated_amount'))
            rec.ftiq_allocated_amount = allocated
            rec.ftiq_unallocated_amount = (rec.amount or 0.0) - allocated
            rec.ftiq_open_invoice_count = len(rec._get_ftiq_open_invoices()) if rec.is_field_collection and rec.partner_id else 0

    @api.onchange('partner_id', 'amount', 'is_field_collection')
    def _onchange_ftiq_collection_defaults(self):
        for rec in self:
            if not rec.is_field_collection:
                continue
            if not rec.partner_id:
                rec.ftiq_collection_line_ids = [Command.clear()]
                continue
            partner_changed = any(
                line.invoice_id
                and line.invoice_id.partner_id.commercial_partner_id != rec.partner_id.commercial_partner_id
                for line in rec.ftiq_collection_line_ids
            )
            if partner_changed or not rec.ftiq_collection_line_ids:
                rec.ftiq_collection_line_ids = rec._prepare_ftiq_open_invoice_commands()
            elif not any(rec.ftiq_collection_line_ids.mapped('allocated_amount')):
                rec._redistribute_ftiq_allocations(in_memory=True)

    @api.constrains('is_field_collection', 'payment_type', 'partner_type')
    def _check_ftiq_collection_type(self):
        for rec in self.filtered('is_field_collection'):
            if rec.payment_type != 'inbound' or rec.partner_type != 'customer':
                raise ValidationError(_('Field collections must be inbound customer payments.'))

    @api.constrains('is_field_collection', 'partner_id', 'amount', 'ftiq_collection_line_ids', 'ftiq_collection_line_ids.allocated_amount')
    def _check_ftiq_collection_allocations(self):
        for rec in self.filtered('is_field_collection'):
            total_allocated = 0.0
            for line in rec.ftiq_collection_line_ids:
                if line.allocated_amount < 0:
                    raise ValidationError(_('Allocated amounts cannot be negative.'))
                if line.invoice_id and rec.partner_id and line.invoice_id.partner_id.commercial_partner_id != rec.partner_id.commercial_partner_id:
                    raise ValidationError(_('Every allocated invoice must belong to the selected customer.'))
                if line.invoice_id and rec.currency_id.compare_amounts(line.allocated_amount, line.invoice_residual_payment) > 0:
                    raise ValidationError(_('Allocated amount cannot exceed the invoice residual amount.'))
                total_allocated += line.allocated_amount
            if rec.currency_id.compare_amounts(total_allocated, rec.amount or 0.0) > 0:
                raise ValidationError(_('Total allocated amount cannot exceed the payment amount.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_field_collection'):
                visit = self.env['ftiq.visit'].browse(vals.get('ftiq_visit_id'))
                vals.setdefault('ftiq_user_id', vals.get('user_id') or (visit.user_id.id if visit else self.env.uid))
                if not vals.get('ftiq_attendance_id'):
                    attendance = self._find_ftiq_attendance(
                        vals.get('ftiq_user_id'),
                        vals.get('date') or fields.Date.context_today(self),
                    )
                    if attendance:
                        vals['ftiq_attendance_id'] = attendance.id
        records = super().create(vals_list)
        for rec in records.filtered('is_field_collection'):
            if rec.partner_id and not rec.ftiq_collection_line_ids:
                rec.action_ftiq_reload_invoices()
            rec._sync_invoice_ids_from_collection_lines()
        return records

    def write(self, vals):
        result = super().write(vals)
        if any(key in vals for key in ('is_field_collection', 'partner_id')):
            field_collections = self.filtered(lambda rec: rec.is_field_collection and rec.partner_id)
            for rec in field_collections:
                if any(
                    line.invoice_id.partner_id.commercial_partner_id != rec.partner_id.commercial_partner_id
                    for line in rec.ftiq_collection_line_ids.filtered('invoice_id')
                ):
                    rec.action_ftiq_reload_invoices()
        if any(key in vals for key in ('is_field_collection', 'partner_id', 'ftiq_collection_line_ids')):
            self.filtered('is_field_collection')._sync_invoice_ids_from_collection_lines()
        return result

    def action_ftiq_reload_invoices(self):
        for rec in self.filtered(lambda payment: payment.is_field_collection and payment.partner_id):
            rec.write({
                'ftiq_collection_line_ids': [Command.clear(), *rec._prepare_ftiq_open_invoice_commands()],
            })
            rec._sync_invoice_ids_from_collection_lines()

    def action_ftiq_distribute_amount(self):
        self.filtered('is_field_collection')._redistribute_ftiq_allocations(in_memory=False)

    def action_ftiq_collect(self):
        for rec in self:
            if rec.ftiq_collection_state != 'draft':
                raise UserError(_('Only draft collections can be marked as collected.'))
        self._capture_ftiq_location_from_context()
        self._ensure_ftiq_operational_attendance()
        draft_payments = self.filtered(lambda rec: rec.state == 'draft')
        if draft_payments:
            draft_payments.action_post()
        self.write({'ftiq_collection_state': 'collected'})
        self._complete_ftiq_tasks()

    def action_ftiq_deposit(self):
        for rec in self:
            if rec.ftiq_collection_state != 'collected':
                raise UserError(_('Only collected payments can be marked as deposited.'))
        self.write({'ftiq_collection_state': 'deposited'})

    def action_ftiq_verify(self):
        for rec in self:
            if rec.ftiq_collection_state != 'deposited':
                raise UserError(_('Only deposited payments can be verified.'))
        self.write({'ftiq_collection_state': 'verified'})

    def action_post(self):
        field_collections = self.filtered('is_field_collection')
        field_collections._capture_ftiq_location_from_context()
        field_collections._ensure_ftiq_operational_attendance()
        field_collections._validate_ftiq_collection_before_post()
        result = super().action_post()
        posted_collections = field_collections.filtered(lambda payment: payment.state in FTIQ_PAYMENT_POSTED_STATES and payment.move_id)
        posted_collections._sync_invoice_ids_from_collection_lines()
        posted_collections._reconcile_ftiq_collection_allocations()
        posted_collections.filtered(lambda payment: payment.ftiq_collection_state == 'draft').write({
            'ftiq_collection_state': 'collected',
        })
        posted_collections._complete_ftiq_tasks()
        return result

    def _validate_ftiq_collection_before_post(self):
        for rec in self.filtered('is_field_collection'):
            if not rec.partner_id:
                raise UserError(_('A customer is required before posting a field collection.'))
            if not rec.amount or rec.amount <= 0:
                raise UserError(_('Collection amount must be greater than zero.'))
            if rec.currency_id.compare_amounts(rec.ftiq_allocated_amount, rec.amount) > 0:
                raise UserError(_('Allocated invoice amounts cannot exceed the collection amount.'))
            open_invoices = rec._get_ftiq_open_invoices()
            positive_allocations = rec.ftiq_collection_line_ids.filtered(lambda line: line.allocated_amount > 0)
            if open_invoices and not positive_allocations:
                raise UserError(_('Allocate at least one open invoice before posting the collection.'))

    def _sync_invoice_ids_from_collection_lines(self):
        for rec in self.filtered('is_field_collection'):
            invoices = rec.ftiq_collection_line_ids.filtered('invoice_id').mapped('invoice_id')
            rec.invoice_ids = [Command.set(invoices.ids)]

    def _complete_ftiq_tasks(self):
        tasks = self.filtered(
            lambda payment: payment.ftiq_daily_task_id
            and payment.ftiq_daily_task_id.state not in ('completed', 'cancelled')
            and payment.state in FTIQ_PAYMENT_POSTED_STATES
        ).mapped('ftiq_daily_task_id')
        if tasks:
            tasks.write({
                'state': 'completed',
                'completed_date': fields.Datetime.now(),
            })

    @api.model
    def _find_ftiq_attendance(self, user_id, attendance_date):
        if not user_id or not attendance_date:
            return self.env['ftiq.field.attendance']
        attendance_date = fields.Date.to_date(attendance_date)
        return self.env['ftiq.field.attendance'].search([
            ('user_id', '=', user_id),
            ('date', '=', attendance_date),
            ('state', '=', 'checked_in'),
        ], limit=1)

    def _capture_ftiq_location_from_context(self):
        ctx = self.env.context
        latitude = ctx.get('ftiq_latitude')
        longitude = ctx.get('ftiq_longitude')
        if not latitude or not longitude:
            return
        for rec in self.filtered(lambda payment: payment.is_field_collection):
            vals = {}
            if not rec.ftiq_latitude:
                vals['ftiq_latitude'] = latitude
            if not rec.ftiq_longitude:
                vals['ftiq_longitude'] = longitude
            if vals:
                rec.write(vals)

    def _ensure_ftiq_operational_attendance(self):
        Attendance = self.env['ftiq.field.attendance']
        ctx = self.env.context
        accuracy = ctx.get('ftiq_accuracy', 0)
        is_mock = ctx.get('ftiq_is_mock', False)
        for rec in self.filtered('is_field_collection'):
            if rec.ftiq_attendance_id:
                continue
            attendance = Attendance.get_active_attendance(rec.ftiq_user_id.id, rec.date)
            if not attendance:
                attendance = Attendance.ensure_operation_attendance(
                    rec.ftiq_user_id.id,
                    attendance_date=rec.date,
                    latitude=rec.ftiq_latitude or ctx.get('ftiq_latitude'),
                    longitude=rec.ftiq_longitude or ctx.get('ftiq_longitude'),
                    accuracy=accuracy,
                    is_mock=is_mock,
                    entry_reference=f'{rec._name},{rec.id}',
                )
            rec.ftiq_attendance_id = attendance.id

    def _get_ftiq_open_invoice_domain(self):
        self.ensure_one()
        if not self.partner_id:
            return [('id', '=', False)]
        return [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
            ('partner_id', 'child_of', self.partner_id.commercial_partner_id.id),
            ('amount_residual', '>', 0),
        ]

    def _get_ftiq_open_invoices(self):
        self.ensure_one()
        return self.env['account.move'].search(
            self._get_ftiq_open_invoice_domain(),
            order='invoice_date_due asc, invoice_date asc, id asc',
        )

    def _prepare_ftiq_open_invoice_commands(self):
        self.ensure_one()
        commands = []
        remaining_amount = self.amount or 0.0
        for invoice in self._get_ftiq_open_invoices():
            residual_in_payment_currency = invoice.currency_id._convert(
                invoice.amount_residual,
                self.currency_id,
                self.company_id,
                self.date or fields.Date.context_today(self),
            )
            allocated_amount = 0.0
            if remaining_amount > 0:
                allocated_amount = min(residual_in_payment_currency, remaining_amount)
                remaining_amount -= allocated_amount
            commands.append(Command.create({
                'invoice_id': invoice.id,
                'allocated_amount': allocated_amount,
            }))
        return commands

    def _redistribute_ftiq_allocations(self, in_memory=False):
        for rec in self.filtered('is_field_collection'):
            lines = rec.ftiq_collection_line_ids.sorted(lambda line: (
                line.due_date or line.invoice_date or fields.Date.today(),
                line.id,
            ))
            if not lines and not in_memory and rec.partner_id:
                rec.action_ftiq_reload_invoices()
                lines = rec.ftiq_collection_line_ids.sorted(lambda line: (
                    line.due_date or line.invoice_date or fields.Date.today(),
                    line.id,
                ))
            remaining_amount = rec.amount or 0.0
            for line in lines:
                allocated_amount = 0.0
                if remaining_amount > 0:
                    allocated_amount = min(line.invoice_residual_payment, remaining_amount)
                    remaining_amount -= allocated_amount
                if in_memory:
                    line.allocated_amount = allocated_amount
                else:
                    line.write({'allocated_amount': allocated_amount})

    def _get_ftiq_counterpart_line(self):
        self.ensure_one()
        liquidity_lines, counterpart_lines, writeoff_lines = self._seek_for_lines()
        return (counterpart_lines + writeoff_lines).filtered(
            lambda line: line.account_id.account_type in FTIQ_RECONCILABLE_ACCOUNT_TYPES and not line.reconciled
        )[:1]

    def _convert_ftiq_amount_to_company(self, amount):
        self.ensure_one()
        return self.currency_id._convert(
            amount,
            self.company_id.currency_id,
            self.company_id,
            self.date or fields.Date.context_today(self),
        )

    def _build_ftiq_reconciliation_values(self, move_line, company_amount):
        self.ensure_one()
        sign = 1.0 if move_line.balance > 0 else -1.0
        company_amount = abs(company_amount)
        absolute_residual = abs(move_line.amount_residual)
        if move_line.currency_id and move_line.currency_id != move_line.company_currency_id and absolute_residual:
            ratio = min(company_amount / absolute_residual, 1.0)
            absolute_currency_amount = move_line.currency_id.round(abs(move_line.amount_residual_currency) * ratio)
        else:
            absolute_currency_amount = company_amount
        return {
            'aml': move_line,
            'amount_residual': sign * company_amount,
            'amount_residual_currency': sign * absolute_currency_amount,
        }

    def _reconcile_ftiq_collection_allocations(self):
        aml_model = self.env['account.move.line']
        partial_model = self.env['account.partial.reconcile']
        for rec in self:
            payment_line = rec._get_ftiq_counterpart_line()
            if not payment_line:
                continue
            remaining_payment_company = abs(payment_line.amount_residual)
            for allocation in rec.ftiq_collection_line_ids.filtered(lambda line: line.remaining_amount > 0 and line.invoice_id):
                remaining_allocation_company = rec._convert_ftiq_amount_to_company(allocation.remaining_amount)
                for invoice_line in allocation._get_candidate_invoice_lines(account=payment_line.account_id):
                    if remaining_payment_company <= 0 or remaining_allocation_company <= 0:
                        break
                    invoice_company_residual = abs(invoice_line.amount_residual)
                    step_company_amount = min(
                        remaining_payment_company,
                        remaining_allocation_company,
                        invoice_company_residual,
                    )
                    if rec.company_currency_id.is_zero(step_company_amount):
                        continue
                    debit_values = rec._build_ftiq_reconciliation_values(invoice_line, step_company_amount)
                    credit_values = rec._build_ftiq_reconciliation_values(payment_line, step_company_amount)
                    result = aml_model.with_context(no_exchange_difference=True)._prepare_reconciliation_single_partial(
                        debit_values,
                        credit_values,
                    )
                    partial_values = result.get('partial_values')
                    if not partial_values:
                        continue
                    partial_model.create(partial_values)
                    remaining_payment_company -= partial_values['amount']
                    remaining_allocation_company -= partial_values['amount']
                    if rec.company_currency_id.is_zero(remaining_payment_company):
                        break


class FtiqCollectionLine(models.Model):
    _name = 'ftiq.collection.line'
    _description = 'Field Collection Invoice Allocation'
    _order = 'due_date asc, invoice_date asc, id asc'

    payment_id = fields.Many2one('account.payment', required=True, ondelete='cascade')
    invoice_id = fields.Many2one('account.move', required=True, ondelete='restrict')
    partner_id = fields.Many2one(related='payment_id.partner_id', store=True)
    payment_currency_id = fields.Many2one(related='payment_id.currency_id')
    invoice_currency_id = fields.Many2one(related='invoice_id.currency_id')
    invoice_date = fields.Date(related='invoice_id.invoice_date', store=True)
    due_date = fields.Date(related='invoice_id.invoice_date_due', store=True)
    invoice_payment_state = fields.Selection(related='invoice_id.payment_state')
    invoice_residual = fields.Monetary(
        string='Invoice Residual',
        currency_field='invoice_currency_id',
        compute='_compute_amounts',
    )
    invoice_residual_payment = fields.Monetary(
        string='Residual In Payment Currency',
        currency_field='payment_currency_id',
        compute='_compute_amounts',
    )
    allocated_amount = fields.Monetary(string='Allocated Amount', currency_field='payment_currency_id', default=0.0)
    reconciled_amount = fields.Monetary(
        string='Reconciled Amount',
        currency_field='payment_currency_id',
        compute='_compute_amounts',
    )
    remaining_amount = fields.Monetary(
        string='Remaining Amount',
        currency_field='payment_currency_id',
        compute='_compute_amounts',
    )

    _sql_constraints = [
        ('ftiq_collection_invoice_unique', 'unique(payment_id, invoice_id)', 'The same invoice cannot be allocated twice in one collection.'),
    ]

    @api.depends(
        'payment_id.date',
        'payment_id.currency_id',
        'payment_id.move_id.line_ids.matched_debit_ids',
        'payment_id.move_id.line_ids.matched_credit_ids',
        'invoice_id.amount_residual',
        'allocated_amount',
    )
    def _compute_amounts(self):
        for rec in self:
            rec.invoice_residual = rec.invoice_id.amount_residual if rec.invoice_id else 0.0
            rec.invoice_residual_payment = 0.0
            rec.reconciled_amount = 0.0
            rec.remaining_amount = rec.allocated_amount
            if not rec.invoice_id or not rec.payment_id:
                continue
            payment = rec.payment_id
            rec.invoice_residual_payment = rec.invoice_id.currency_id._convert(
                rec.invoice_id.amount_residual,
                payment.currency_id,
                payment.company_id,
                payment.date or fields.Date.context_today(payment),
            )
            if not payment.move_id:
                continue
            payment_lines = payment._seek_for_lines()[1].filtered(
                lambda line: line.account_id.account_type in FTIQ_RECONCILABLE_ACCOUNT_TYPES
            )
            invoice_lines = rec._get_candidate_invoice_lines(include_reconciled=True)
            partials = (payment_lines.matched_debit_ids + payment_lines.matched_credit_ids).filtered(
                lambda partial: partial.debit_move_id in invoice_lines or partial.credit_move_id in invoice_lines
            )
            reconciled_company_amount = sum(partials.mapped('amount'))
            rec.reconciled_amount = payment.company_id.currency_id._convert(
                reconciled_company_amount,
                payment.currency_id,
                payment.company_id,
                payment.date or fields.Date.context_today(payment),
            )
            rec.remaining_amount = max(rec.allocated_amount - rec.reconciled_amount, 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped('payment_id')._sync_invoice_ids_from_collection_lines()
        return records

    def write(self, vals):
        payments = self.mapped('payment_id')
        result = super().write(vals)
        (payments | self.mapped('payment_id'))._sync_invoice_ids_from_collection_lines()
        return result

    def unlink(self):
        payments = self.mapped('payment_id')
        result = super().unlink()
        payments._sync_invoice_ids_from_collection_lines()
        return result

    def _get_candidate_invoice_lines(self, account=None, include_reconciled=False):
        self.ensure_one()
        lines = self.invoice_id.line_ids.filtered(
            lambda line: line.account_id.account_type in FTIQ_RECONCILABLE_ACCOUNT_TYPES
        )
        if not include_reconciled:
            lines = lines.filtered(lambda line: not line.reconciled)
        if account:
            lines = lines.filtered(lambda line: line.account_id == account)
        return lines.sorted(lambda line: (
            line.date_maturity or line.date or fields.Date.today(),
            line.id,
        ))
