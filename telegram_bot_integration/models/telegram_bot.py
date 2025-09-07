# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
import logging

_logger = logging.getLogger(__name__)

class TelegramBot(models.Model):
    _name = 'telegram.bot'
    _description = 'Telegram Bot Configuration'

    name = fields.Char(string='Bot Name', required=True)
    token = fields.Char(string='Bot Token', required=True)
    webhook_url = fields.Char(string='Webhook URL', compute='_compute_webhook_url')
    active = fields.Boolean(string='Active', default=True)
    chat_ids = fields.One2many('telegram.chat', 'bot_id', string='Chats')

    @api.depends('token')
    def _compute_webhook_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for bot in self:
            if bot.token:
                bot.webhook_url = f"{base_url}/telegram/webhook/{bot.id}"
            else:
                bot.webhook_url = False

    def set_webhook(self):
        self.ensure_one()
        if not self.token:
            raise UserError("Please set the bot token first.")
        
        url = f"https://api.telegram.org/bot{self.token}/setWebhook"
        data = {
            'url': self.webhook_url,
            'drop_pending_updates': True
        }
        
        try:
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get('ok'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': 'Webhook set successfully!',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(f"Failed to set webhook: {result.get('description')}")
                
        except Exception as e:
            raise UserError(f"Error setting webhook: {str(e)}")

    def send_message(self, chat_id, message, parse_mode='HTML'):
        """Send message to Telegram chat"""
        self.ensure_one()
        if not self.token:
            raise UserError("Bot token not configured")
        
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': parse_mode
        }
        
        try:
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            _logger.error(f"Error sending Telegram message: {str(e)}")
            return None

class TelegramChat(models.Model):
    _name = 'telegram.chat'
    _description = 'Telegram Chat'

    chat_id = fields.Char(string='Chat ID', required=True)
    username = fields.Char(string='Username')
    first_name = fields.Char(string='First Name')
    last_name = fields.Char(string='Last Name')
    bot_id = fields.Many2one('telegram.bot', string='Bot', required=True)
    active = fields.Boolean(string='Active', default=True)
    
    # الحقول الجديدة لربط المستخدم بأودو
    partner_id = fields.Many2one('res.partner', string='Customer')
    user_id = fields.Many2one('res.users', string='User')
