{
    'name': 'Custom Payment Discount',
    'version': '1.0',
    'summary': 'Add cash discount handling for payments.',
    'description': 'Enhances the Account Payment module by allowing cash discount handling, including adding cash discount and discount account fields to the payment form.',
    'author': 'Your Name',
    'website': 'https://yourwebsite.com',
    'category': 'Accounting',
    'depends': ['account'],  # Ensure it depends on the `account` module
    'data': [
        'security/ir.model.access.csv',         # Access rights file
        'views/account_payment_views.xml',      # View file for adding fields to the form
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',  # Define the module's license
}
