{
    'name': 'Account Custom Field',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Add custom computed field to account move lines',
    'description': """
        This module adds a custom field to account move lines that displays either the amount in currency or the difference between debit and credit.
    """,
    'author': 'Your Name',
    'depends': ['account'],
    'data': [
        'views/account_move_line_view.xml',
    ],
    'installable': True,
    'application': False,
}
