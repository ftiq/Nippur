{
    'name': 'Sales Representative Integration',
    'version': '1.0',
    'summary': 'Add Sales Representative and Gifts directly in Sales and Invoices',
    'description': 'Integrates custom fields for sales representatives and gifts into Sales and Invoices.',
    'author': 'Your Name',
    'depends': ['sale', 'account'],
    'data': [
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
}
