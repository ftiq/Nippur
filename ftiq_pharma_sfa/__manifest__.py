{
    'name': 'FTIQ sale management',
    'version': '18.0.2.0.0',
    'category': 'Sales',
    'summary': 'Pharmaceutical Sales Force Automation - Integrated with Sales, Accounting, Inventory & Expenses',
    'description': """
FTIQ Pharma SFA - Pharmaceutical Sales Force Automation
========================================================
Integrated field sales management system:
- Sales (sale.order) - Field sales orders
- Accounting (account.move / account.payment) - Invoices and collections
- Inventory (stock.picking) - Automatic delivery
- Expenses (hr.expense) - Field rep expenses
- Projects (project) - Task management

Features:
- GPS field attendance tracking
- Doctor and pharmacy visits with GPS tracking
- Field orders -> automatic invoice -> automatic delivery
- Cash collections -> real accounting payments
- Client shelf stock checks
- Sales targets and automatic KPI
- Weekly plans and daily tasks
- Marketing materials
- Reports and analytics
    """,
    'author': "Salah Alhjany",
    'website': "https://wa.me/967711778764",
    'depends': [
        'base',
        'mail',
        'product',
        'contacts',
        'sales_team',
        'sale_management',
        'sale_stock',
        'purchase',
        'account',
        'hr_expense',
        'stock',
        'project',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/ir_sequence_data.xml',
        'data/client_category_data.xml',
        'data/task_profile_data.xml',
        'data/firebase_config_data.xml',
       'demo/demo_data.xml',
    'demo/demo_team_data.xml',
      # 'demo/demo_operational_data.xml',
       #'demo/demo_arabic_showcase.xml',



        'views/dashboard_views.xml',
        'views/config_views.xml',
        'views/mobile_runtime_views.xml',
        'views/client_question_views.xml',
        'views/res_partner_views.xml',
        'views/field_attendance_views.xml',
        'views/marketing_material_views.xml',
        'views/sale_order_views.xml',
        'views/account_payment_views.xml',
        'views/account_move_views.xml',
        'views/hr_expense_views.xml',
        'views/stock_check_views.xml',
        'views/sales_target_views.xml',
        'views/daily_task_views.xml',
        'views/project_views.xml',
        'views/visit_views.xml',
        'views/weekly_plan_views.xml',
        'views/plan_wizard_views.xml',
        'views/team_message_views.xml',
        'views/menu_views.xml',
        'report/visit_report.xml',
        'report/visit_report_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ftiq_pharma_sfa/static/src/js/geolocation.js',
            'ftiq_pharma_sfa/static/src/xml/geolocation.xml',
            'ftiq_pharma_sfa/static/src/js/dashboard.js',
            'ftiq_pharma_sfa/static/src/xml/dashboard.xml',
            'ftiq_pharma_sfa/static/src/js/mobile_client_search.js',
            'ftiq_pharma_sfa/static/src/xml/mobile_client_search.xml',
            'ftiq_pharma_sfa/static/src/css/mobile_shell.css',
            'ftiq_pharma_sfa/static/src/css/mobile_client_search.css',
            'ftiq_pharma_sfa/static/src/css/dashboard.css',
            'ftiq_pharma_sfa/static/src/js/plan_geo_map_field.js',
            'ftiq_pharma_sfa/static/src/xml/plan_geo_map_field.xml',
            'ftiq_pharma_sfa/static/src/css/plan_wizard.css',
            'ftiq_pharma_sfa/static/src/css/geo_map.css',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
