{
    'name': 'Account Discount Columns',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Add discount and total columns to journal items',
    'description': """
        This module adds two columns to account move lines:
        - Discount Amount: Shows the discount amount 
        - Gross Total: Shows net amount + discount (original amount before discount)
    """,
    'author': "Engineer/Saleh Alhjany",
    'website': "https://www.facebook.com/salh.alhjany/?rdid=plWVCqF0AkDERe3g",
    'license': 'LGPL-3',
    'depends': ['account', 'sale'],
    'data': [
        'views/account_move_line_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
