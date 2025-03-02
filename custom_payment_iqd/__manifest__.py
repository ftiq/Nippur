{
    'name': 'Custom Payment and Sale Order IQD/USD Balances',
    'version': '1.0',
    'summary': 'Adds IQD/USD balance fields to Account Payment and Sale Order.',
    'depends': ['account', 'sale'],  # Required dependencies
    'data': [
        'views/account_payment_view.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
