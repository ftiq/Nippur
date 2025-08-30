# -*- coding: utf-8 -*-
{
    'name': "Account Move Line Discount",
    'summary': "Add discount amount column to journal entries view",
    'description': """

    """,
    'author': "Engineer / Salah Alhjany",
    'website': "https://www.facebook.com/salh.alhjany/?rdid=plWVCqF0AkDERe3g",
    'category': 'Accounting',
    'version': '18.0.1.0.0',
    'depends': [
        'account',
        'sale',
        'base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_line_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
