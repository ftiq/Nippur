{
    "name": "FTIQ CRM Mobile API",
    "version": "18.0.1.0.0",
    "category": "Sales/CRM",
    "summary": "ftiq CRM compatible mobile API backed by standard Odoo models",
    "description": """

    """,
    "author": "Salah Alhjany",
    "website": "https://wa.me/967711778764",
    "depends": [
        "web",
        "contacts",
        "base_geolocalize",
        "crm",
        "sale",
        "sales_team",
        "project",
        "account",
        "mail",
    ],
    "assets": {
        "web.assets_backend": [
            "ftiq_crm_mobile_api/static/src/css/chatter_overrides.css",
        ],
    },
    "data": [
        "security/ir.model.access.csv",
        "data/firebase_config_data.xml",
        "views/crm_mobile_location_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
