from datetime import timedelta

from odoo import fields, http
from odoo.http import request


FTIQ_DASHBOARD_PAYMENT_STATES = ('in_process', 'paid')
FTIQ_DASHBOARD_TASK_TERMINAL_STATES = ('completed', 'confirmed', 'cancelled')


class FtiqDashboardController(http.Controller):

    @http.route('/ftiq_pharma_sfa/dashboard_data', type='json', auth='user')
    def get_dashboard_data(self):
        env = request.env
        user = env.user
        today = fields.Date.context_today(user)
        month_start = today.replace(day=1)
        next_month_start = (month_start + timedelta(days=32)).replace(day=1)
        month_end = next_month_start - timedelta(days=1)
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        role, scope_users = self._get_scope_users(user)
        scope_user_ids = scope_users.ids or [user.id]

        Visit = env['ftiq.visit']
        PlanLine = env['ftiq.weekly.plan.line']
        SaleOrder = env['sale.order']
        Payment = env['account.payment']
        Attendance = env['ftiq.field.attendance']
        DailyTask = env['ftiq.daily.task']
        StockCheck = env['ftiq.stock.check']
        Invoice = env['account.move']
        Partner = env['res.partner']
        Target = env['ftiq.sales.target']
        ActivityFeed = env['ftiq.activity.feed']

        visit_scope_domain = [('user_id', 'in', scope_user_ids)]
        plan_scope_domain = [('user_id', 'in', scope_user_ids)]
        order_scope_domain = [('user_id', 'in', scope_user_ids), ('is_field_order', '=', True)]
        payment_scope_domain = [('ftiq_user_id', 'in', scope_user_ids), ('is_field_collection', '=', True)]
        attendance_scope_domain = [('user_id', 'in', scope_user_ids)]
        task_scope_domain = [('user_id', 'in', scope_user_ids)]
        invoice_scope_domain = [('ftiq_access_user_id', 'in', scope_user_ids), ('is_field_invoice', '=', True)]

        month_start_dt = fields.Datetime.to_datetime(month_start)
        next_month_dt = fields.Datetime.to_datetime(next_month_start)
        today_dt = fields.Datetime.to_datetime(today)
        tomorrow_dt = today_dt + timedelta(days=1)

        visits_today = Visit.search(visit_scope_domain + [
            ('visit_date', '=', today),
            ('state', 'in', ('in_progress', 'submitted', 'approved', 'returned')),
        ])
        approved_visits_month = Visit.search(visit_scope_domain + [
            ('visit_date', '>=', month_start),
            ('visit_date', '<=', month_end),
            ('state', '=', 'approved'),
        ])
        pending_visits = Visit.search(visit_scope_domain + [('state', '=', 'submitted')])
        plan_lines_month = PlanLine.search(plan_scope_domain + [
            ('scheduled_date', '>=', month_start),
            ('scheduled_date', '<=', month_end),
        ])
        plan_lines_today = plan_lines_month.filtered(lambda line: line.scheduled_date == today)
        completed_plan_lines = plan_lines_month.filtered(lambda line: line.state == 'completed')
        missed_plan_lines = plan_lines_month.filtered(lambda line: line.state == 'missed')

        orders_month = SaleOrder.search(order_scope_domain + [
            ('date_order', '>=', month_start_dt),
            ('date_order', '<', next_month_dt),
            ('state', 'in', ('sale', 'done')),
        ])

        collections_month = Payment.search(payment_scope_domain + [
            ('date', '>=', month_start),
            ('date', '<=', month_end),
            ('state', 'in', FTIQ_DASHBOARD_PAYMENT_STATES),
        ])

        open_invoices = Invoice.search(invoice_scope_domain + [
            ('state', '=', 'posted'),
            ('amount_residual', '>', 0),
        ])

        attendance_today = Attendance.search(attendance_scope_domain + [
            ('date', '=', today),
            ('state', '=', 'checked_in'),
        ])

        module_task_domain = self._module_task_domain()
        tasks_pending = DailyTask.search(task_scope_domain + module_task_domain + [('state', 'in', ('draft', 'pending', 'in_progress', 'submitted', 'returned'))])
        tasks_today = DailyTask.search(task_scope_domain + module_task_domain + [
            ('scheduled_date', '>=', today_dt),
            ('scheduled_date', '<', tomorrow_dt),
        ], order='scheduled_date asc, priority desc', limit=8)
        tasks_completed_month = DailyTask.search(task_scope_domain + module_task_domain + [
            ('state', 'in', ('completed', 'confirmed')),
            ('completed_date', '>=', month_start_dt),
            ('completed_date', '<', next_month_dt),
        ])
        overdue_tasks = DailyTask.search(task_scope_domain + module_task_domain + [
            ('state', 'not in', FTIQ_DASHBOARD_TASK_TERMINAL_STATES),
            ('scheduled_date', '<', fields.Datetime.now()),
        ])

        stock_checks_month = StockCheck.search(task_scope_domain + [
            ('check_date', '>=', month_start_dt),
            ('check_date', '<', next_month_dt),
        ])
        reviewed_stock_checks = stock_checks_month.filtered(lambda check: check.state == 'reviewed')

        active_targets = Target.search([
            ('state', '=', 'active'),
            ('user_id', 'in', scope_user_ids),
        ]).sorted(
            key=lambda target: (target.achievement_rate, target.id),
            reverse=True,
        )[:6]

        new_clients_month = Partner.search_count([
            '|',
            ('user_id', 'in', scope_user_ids),
            '&',
            ('user_id', '=', False),
            ('create_uid', 'in', scope_user_ids),
            ('create_date', '>=', month_start_dt),
            ('create_date', '<', next_month_dt),
            '|', '|',
            ('is_ftiq_doctor', '=', True),
            ('is_ftiq_center', '=', True),
            ('is_ftiq_pharmacy', '=', True),
        ])

        active_partner_ids = set(approved_visits_month.mapped('partner_id').ids)
        active_partner_ids.update(orders_month.mapped('partner_id').ids)
        active_partner_ids.update(collections_month.mapped('partner_id').ids)

        average_visit_duration = (
            sum(approved_visits_month.mapped('duration')) / len(approved_visits_month)
            if approved_visits_month else 0.0
        )
        plan_compliance = (
            len(completed_plan_lines) / len(plan_lines_month) * 100.0
            if plan_lines_month else 0.0
        )
        collection_ratio = (
            sum(collections_month.mapped('amount')) / sum(orders_month.mapped('amount_total')) * 100.0
            if orders_month and sum(orders_month.mapped('amount_total')) else 0.0
        )
        month_progress = plan_compliance

        area_rows = self._build_area_rows(
            plan_lines_month,
            approved_visits_month,
            orders_month,
            collections_month,
            open_invoices,
        )
        team_rows = self._build_team_rows(
            scope_users,
            plan_lines_month,
            approved_visits_month,
            orders_month,
            collections_month,
            attendance_today,
            overdue_tasks,
        )

        return {
            'role': role,
            'user_name': user.name,
            'period_label': month_start.strftime('%B %Y'),
            'date_label': str(today),
            'current_datetime': fields.Datetime.to_string(fields.Datetime.now()),
            'month_start': str(month_start),
            'month_end': str(month_end),
            'next_month_start': str(next_month_start),
            'scope_user_ids': scope_user_ids,
            'currency_symbol': env.company.currency_id.symbol or '',
            'month_progress': month_progress,
            'kpis': {
                'visits_today': len(visits_today),
                'approved_visits_month': len(approved_visits_month),
                'pending_approvals': len(pending_visits),
                'planned_month': len(plan_lines_month),
                'completed_month': len(completed_plan_lines),
                'missed_month': len(missed_plan_lines),
                'plan_compliance': plan_compliance,
                'orders_count': len(orders_month),
                'orders_amount': sum(orders_month.mapped('amount_total')),
                'collections_count': len(collections_month),
                'collections_amount': sum(collections_month.mapped('amount')),
                'stock_checks_count': len(stock_checks_month),
                'collection_ratio': collection_ratio,
                'open_invoice_count': len(open_invoices),
                'open_invoice_amount': sum(open_invoices.mapped('amount_residual')),
                'checked_in_now': len(attendance_today),
                'team_size': len(scope_users),
                'active_clients': len(active_partner_ids),
                'new_clients': new_clients_month,
                'overdue_tasks': len(overdue_tasks),
                'pending_approvals': len(pending_visits),
                'targets_active': len(active_targets),
                'average_visit_duration': average_visit_duration,
                'reviewed_stock_checks': len(reviewed_stock_checks),
            },
            'status_board': [
                {
                    'label': 'Today Plan',
                    'value': len(plan_lines_today),
                    'secondary': len(plan_lines_today.filtered(lambda line: line.state == 'completed')),
                    'secondary_label': 'completed',
                    'tone': 'primary',
                },
                {
                    'label': 'Pending Tasks',
                    'value': len(tasks_pending),
                    'secondary': len(tasks_completed_month),
                    'secondary_label': 'completed this month',
                    'tone': 'warning',
                },
                {
                    'label': 'Stock Checks',
                    'value': len(stock_checks_month),
                    'secondary': len(reviewed_stock_checks),
                    'secondary_label': 'reviewed',
                    'tone': 'info',
                },
                {
                    'label': 'Open Invoices',
                    'value': sum(open_invoices.mapped('amount_residual')),
                    'secondary': len(open_invoices),
                    'secondary_label': 'open invoices',
                    'tone': 'danger',
                    'is_currency': True,
                },
            ],
            'alerts': [
                {
                    'label': 'Visits Awaiting Approval',
                    'value': len(pending_visits),
                    'tone': 'warning',
                    'action_key': 'pending_approvals',
                },
                {
                    'label': 'Missed Plan Lines',
                    'value': len(missed_plan_lines),
                    'tone': 'danger',
                    'action_key': 'missed_plan_lines',
                },
                {
                    'label': 'Overdue Tasks',
                    'value': len(overdue_tasks),
                    'tone': 'danger',
                    'action_key': 'overdue_tasks',
                },
                {
                    'label': 'Active Check-ins',
                    'value': len(attendance_today),
                    'tone': 'success',
                    'action_key': 'active_checkins',
                },
            ],
            'targets': [
                {
                    'id': target.id,
                    'name': target.name,
                    'user_id': target.user_id.id,
                    'user_name': target.user_id.name,
                    'target_type': target.target_type,
                    'target_value': target.target_value,
                    'achieved_value': target.achieved_value,
                    'achievement_rate': target.achievement_rate,
                }
                for target in active_targets
            ],
            'area_rows': area_rows,
            'team_rows': team_rows,
            'today_tasks': [
                {
                    'id': task.id,
                    'name': task.name,
                    'task_profile_name': task.task_profile_id.display_name or '',
                    'partner_name': task.partner_id.display_name or 'No client',
                    'scheduled_date': str(task.scheduled_date),
                    'state': task.state,
                    'task_type': task.task_type,
                }
                for task in tasks_today
            ],
            'activity_feed': ActivityFeed.build_feed(scope_user_ids, limit=12),
        }

    def _get_scope_users(self, user):
        Teams = request.env['crm.team']
        is_manager = user.has_group('ftiq_pharma_sfa.group_ftiq_manager')
        is_supervisor = user.has_group('ftiq_pharma_sfa.group_ftiq_supervisor')
        if is_manager:
            teams = Teams.search([])
            scope_users = (teams.mapped('member_ids') | teams.mapped('user_id') | user).filtered(lambda member: not member.share)
            return 'manager', scope_users
        if is_supervisor:
            teams = Teams.search([('user_id', '=', user.id)])
            scope_users = (teams.mapped('member_ids') | user).filtered(lambda member: not member.share)
            return 'supervisor', scope_users
        return 'rep', user

    @staticmethod
    def _module_task_domain():
        return []

    @staticmethod
    def _area_key(record):
        area = record.partner_id.ftiq_area_id or getattr(record, 'partner_area_id', False)
        return area.id if area else 0, area.name if area else 'Unassigned'

    def _build_area_rows(self, plan_lines, visits, orders, collections, invoices):
        area_map = {}

        def bucket(area_id, area_name):
            return area_map.setdefault(area_id, {
                'area_id': area_id,
                'name': area_name,
                'planned': 0,
                'completed': 0,
                'visits': 0,
                'orders_count': 0,
                'orders_amount': 0.0,
                'collections_count': 0,
                'collections_amount': 0.0,
                'outstanding_count': 0,
                'outstanding_amount': 0.0,
                'compliance': 0.0,
            })

        for line in plan_lines:
            area_id, area_name = self._area_key(line)
            row = bucket(area_id, area_name)
            row['planned'] += 1
            if line.state == 'completed':
                row['completed'] += 1

        for visit in visits:
            area_id, area_name = self._area_key(visit)
            bucket(area_id, area_name)['visits'] += 1

        for order in orders:
            area_id, area_name = self._area_key(order)
            row = bucket(area_id, area_name)
            row['orders_count'] += 1
            row['orders_amount'] += order.amount_total

        for payment in collections:
            area_id, area_name = self._area_key(payment)
            row = bucket(area_id, area_name)
            row['collections_count'] += 1
            row['collections_amount'] += payment.amount

        for invoice in invoices:
            area = invoice.partner_id.ftiq_area_id
            area_id = area.id if area else 0
            area_name = area.name if area else 'Unassigned'
            row = bucket(area_id, area_name)
            row['outstanding_count'] += 1
            row['outstanding_amount'] += invoice.amount_residual

        rows = list(area_map.values())
        for row in rows:
            row['compliance'] = (row['completed'] / row['planned'] * 100.0) if row['planned'] else 0.0
        rows.sort(key=lambda row: (row['orders_amount'] + row['collections_amount'], row['planned']), reverse=True)
        return rows[:8]

    def _build_team_rows(self, scope_users, plan_lines, visits, orders, collections, attendance_today, overdue_tasks):
        team_map = {
            user.id: {
                'user_id': user.id,
                'name': user.name,
                'area_name': user.ftiq_area_id.name or '',
                'planned': 0,
                'completed': 0,
                'approved_visits': 0,
                'orders_amount': 0.0,
                'collections_amount': 0.0,
                'checked_in': False,
                'overdue_tasks': 0,
                'compliance': 0.0,
            }
            for user in scope_users
        }

        for line in plan_lines:
            if line.user_id.id not in team_map:
                continue
            team_map[line.user_id.id]['planned'] += 1
            if line.state == 'completed':
                team_map[line.user_id.id]['completed'] += 1

        for visit in visits:
            if visit.user_id.id in team_map:
                team_map[visit.user_id.id]['approved_visits'] += 1

        for order in orders:
            if order.user_id.id in team_map:
                team_map[order.user_id.id]['orders_amount'] += order.amount_total

        for payment in collections:
            if payment.ftiq_user_id.id in team_map:
                team_map[payment.ftiq_user_id.id]['collections_amount'] += payment.amount

        for attendance in attendance_today:
            if attendance.user_id.id in team_map:
                team_map[attendance.user_id.id]['checked_in'] = True

        for task in overdue_tasks:
            if task.user_id.id in team_map:
                team_map[task.user_id.id]['overdue_tasks'] += 1

        rows = list(team_map.values())
        for row in rows:
            row['compliance'] = (row['completed'] / row['planned'] * 100.0) if row['planned'] else 0.0
        rows.sort(
            key=lambda row: (
                row['collections_amount'],
                row['orders_amount'],
                row['approved_visits'],
                row['compliance'],
            ),
            reverse=True,
        )
        return rows[:8]
