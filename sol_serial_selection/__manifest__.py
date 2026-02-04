{
    'name': 'SOL Lot/Serial Number | Multi Lot/Serial Number| Lot/Serial Number on Sales Order line',
    'version': '1.0',
    'sequence': 60,
    'category': 'Extra Tools',
    'author': 'Vashmitha',
    'summary': 'Allow salesperson to select serial numbers in sale order lines',
    'description': """Sale order serial number selection""",
    'depends': ['sale', 'stock'],
    'data': [
        'views/sale_order_line_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}






