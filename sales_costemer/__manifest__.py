{
    'name': 'Sales Representative Integration',
    'version': '1.0',
    'summary': 'Add Sales Representative and Gifts to Sales Orders and Invoices',
    'description': 'Integrates custom fields for sales representatives and gifts into Sales Orders and Invoices.',
    'author': 'Your Name',
    'depends': ['sale', 'account'],
    'data': [
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
}
