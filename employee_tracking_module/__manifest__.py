{
    'name': 'Employee Tracking',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'تتبع مواقع ومشاوير الموظفين',
    'author': 'Future of Technology Iraq',
    'depends': ['hr', 'base'],
    'data': [
        'views/employee_tracking_views.xml',
        'views/security_groups.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'employee_tracking/static/src/js/employee_tracking_map.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}