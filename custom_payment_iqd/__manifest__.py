{
    'name': 'Custom Payment and Sale Order IQD/ USD Sum',
    'version': '1.0',
    'summary': 'Calculates the sum of custom amounts for IQD and USD in customer payments and sales orders.',
    'depends': ['account', 'sale'],  # Add 'sale' as a dependency
    'data': [
        'views/account_payment_view.xml',
        'views/sale_order_view.xml',  # Ensure you include the sale order view file
    ],
    'installable': True,
    'application': False,
    'author': 'Your Name or Company',
    'license': 'LGPL-3',
}
