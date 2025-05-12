{
    'name': 'Location Tracker User',
    'summary': 'Track user location information',
    'description': """
        This module allows tracking and storing user location information.
        Features:
        - Store user location data
        - View location history
        - Track timestamps of locations
    """,
    'category': 'Administration',
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'web'],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'security/ir.model.access.csv',
        'security/user_location_security.xml',
        'views/user_location_log_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'user_location_tracker/static/src/js/track_user_location.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
