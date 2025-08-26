{
    'name': 'Journal Items Report',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Generate PDF reports for Journal Items',
    'author': 'AbdElwahap',
    'depends': ['account'],
    'data': [
        'reports/report_template.xml',
        'data/journal_items_report_data.xml',
        'views/journal_items_views.xml',
    ],
    'application': False,
    'installable': True,
}
