# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions
from datetime import date
from dateutil.relativedelta import relativedelta

class AcademyPlayer(models.Model):
    _name = 'academy.player'
    _description = 'لاعب أكاديمية إسبانيول'

    full_name = fields.Char(string='الاسم الثلاثي', required=True)
    surname = fields.Char(string='اللقب', required=True)
    mother_name = fields.Char(string='اسم الأم')
    birth_date = fields.Date(string='تاريخ الميلاد')
    address = fields.Char(string='العنوان')
    phone = fields.Char(string='رقم الهاتف')
    weight = fields.Float(string='الوزن (كغم)')
    height = fields.Float(string='الطول (سم)')
    visible_marks = fields.Text(string='العلامات الظاهرة')
    pledge_text = fields.Text(string='التعهد الخطي', default='')
    guardian_name = fields.Char(string='ولي أمر اللاعب')
    signed_date = fields.Date(string='تاريخ التوقيع')
    player_image = fields.Binary(string='صورة اللاعب', attachment=True)
    fingerprint_template = fields.Binary(string='قالب البصمة', attachment=True)
    subscription_ids = fields.Many2many(
        'sale.subscription', 'academy_player_subscription_rel',
        'player_id', 'subscription_id', string='الاشتراكات')

    subscription_end_date = fields.Date(
        string='تاريخ انتهاء الاشتراك', compute='_compute_subscription_end', store=True)
    subscription_status = fields.Selection([
        ('active', 'نشط'),
        ('expired', 'منتهي')
    ], string='حالة الاشتراك', compute='_compute_subscription_end', store=True)

    @api.depends('subscription_ids.date_start', 'subscription_ids.recurring_rule_type',
                 'subscription_ids.recurring_interval')
    def _compute_subscription_end(self):
        for player in self:
            latest_end = False
            for sub in player.subscription_ids:
                if sub.recurring_rule_type == 'monthly':
                    end = sub.date_start + relativedelta(months=sub.recurring_interval)
                else:
                    end = sub.date_start
                if not latest_end or end > latest_end:
                    latest_end = end
            player.subscription_end_date = latest_end
            player.subscription_status = 'active' if latest_end and latest_end >= date.today() else 'expired'

    @api.model
    def check_fingerprint_access(self, template):
        if not template:
            raise exceptions.UserError('لم يتم استلام بيانات البصمة')
        players = self.search([('fingerprint_template', '=', template)])
        if not players:
            return {'status': 'error', 'message': 'لا يوجد لاعب مسجل بهذه البصمة'}
        player = players[0]
        player._compute_subscription_end()
        return {
            'status': 'success' if player.subscription_status == 'active' else 'expired',
            'player_id': player.id,
            'message': 'تم السماح بالدخول' if player.subscription_status == 'active' else 'انتهى الاشتراك'
        }
