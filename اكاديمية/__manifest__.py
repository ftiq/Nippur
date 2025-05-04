# -*- coding: utf-8 -*-
{
    'name': 'أكاديمية إسبانيول',
    'version': '1.0',
    'summary': 'تسجيل اللاعبين مع الاشتراكات ودعم البصمة',
    'category': 'Custom',
    'author': 'Your Company',
    'license': 'LGPL-3',
    'depends': ['base', 'sale_subscription', 'web', 'report'],
    'data': [
        'security/ir.model.access.csv',
        'views/player_registration_view.xml',
        'reports/player_registration_report.xml',
    ],
    'installable': True,
    'application': False,
}
