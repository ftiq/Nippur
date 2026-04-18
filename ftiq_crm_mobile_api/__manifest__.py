{
    "name": "FTIQ CRM Mobile API",
    "version": "18.0.1.0.0",
    "category": "Sales/CRM",
    "summary": "ftiq CRM compatible mobile API backed by standard Odoo models",
    "description": """
FTIQ CRM Mobile API
===================

Compatibility API for the BottleCRM Flutter screens.

The module intentionally maps the mobile application's existing Django-style
JSON contracts to standard Odoo models instead of recreating the Flutter
screens or adding parallel CRM tables.
    """,
    "author": "Salah Alhjany",
    "website": "https://wa.me/967711778764",
    "depends": [
        "web",
        "contacts",
        "base_geolocalize",
        "crm",
        "sales_team",
        "project",
        "account",
        "mail",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/firebase_config_data.xml",
        "views/crm_mobile_location_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
