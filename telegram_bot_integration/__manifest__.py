# -*- coding: utf-8 -*-
{
    'name': 'Telegram Bot Integration',
    'version': '1.0',
    'summary': 'Integrate Odoo with Telegram Bot',
    'category': 'Tools',
    'author': 'Your Name',
    'website': 'https://yourwebsite.com',
    'depends': ['base', 'mail'],
    'data': [
        'views/telegram_bot_views.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}