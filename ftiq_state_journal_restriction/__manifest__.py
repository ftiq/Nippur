{
    'name': 'FTIQ State Journal Restriction',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Restrict available journals based on partner state',
    'author': "Salah Alhjany",
    'website': "https://wa.me/967711778764",
    'depends': [
        'account',
    ],
    'data': [
        'views/res_country_state_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
}
