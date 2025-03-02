# -*- coding: utf-8 -*-
{
    'name': "Get Invoice Location",

    'summary': "Get Invoice Location",

    'description': """
            Get Invoice Location
    """,

    'author': "MajedHameed",
    'website': "https://ajabaa.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '18.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base','sale'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/sale_order.xml',
        'views/res_partner.xml'
    ],
    # only loaded in demonstration mode
    'demo': [
        # 'demo/demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mj_customer_invoice_location/static/src/js/get_location.js',
            # 'mj_customer_invoice_location/static/src/js/map_widget.js',
            # 'mj_customer_invoice_location/static/src/xml/map_widget.xml',
            
        ],
    },
}

