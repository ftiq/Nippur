{
    'name': 'Reduce Decimal Places by Currency',
    'version': '1.1',
    'summary': 'Adjust decimal places for journal entries based on currency: 0 for IQD and 2 for USD.',
    'description': """
        This module reduces decimal places in journal entries based on the currency:
        - 0 decimal places for Iraqi Dinar (IQD).
        - 2 decimal places for US Dollar (USD).
        """,
    'category': 'Accounting',
    'author': 'Mhd Manar Zamrik',
    'website': 'https://bt.com.iq',
    'depends': [
        'account',  # Dependency on the Accounting module
    ],
    'data': [
        'views/account_move_line_view.xml',  # Adds a button to run the functionality
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
