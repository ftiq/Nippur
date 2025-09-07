{
    'name': 'Telegram Bot Integration',
    'version': '1.0',
    'summary': 'Integrate Odoo with Telegram Bot',
    'description': """
        This module integrates Odoo with Telegram Messenger.
        Features include:
        - Send messages from Odoo to Telegram
        - Receive messages from Telegram to Odoo
        - Manage multiple bots
        - Webhook configuration
        - Invoice and statement queries
        - Account linking
    """,
    'category': 'Tools',
    'author': 'Your Name',
    'website': 'https://yourwebsite.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/telegram_bot_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
