# -*- coding: utf-8 -*-
{
    'name': "Get Invoice Location",

    'summary': "Get Invoice Location",

    'description': "Get Invoice Location",

    'author': "MajedHameed",
    'website': "https://ajabaa.com",

    'category': 'Uncategorized',

    'depends': ['base', 'sale'],

    'data': [
        'views/sale_order.xml',
        'views/res_partner.xml'
    ],

    'assets': {
        'web.assets_backend': [
            'mj_customer_invoice_location/static/src/js/get_location.js',

        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
