{
    'name': 'Employee Tracking',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'تتبع مواقع ومشاوير الموظفين',
    'author': 'Future of Technology Iraq',
    'depends': ['hr', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'views/employee_trip_views.xml',
        'views/employee_location_views.xml',
        'views/employee_tracking_dashboard.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'your_module/static/src/js/employee_tracking_map.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}