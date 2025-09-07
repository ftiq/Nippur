# -*- coding: utf-8 -*-
import json
import logging
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

class TelegramController(http.Controller):

    @http.route('/telegram/webhook/<int:bot_id>', type='json', auth='public', methods=['POST'], csrf=False)
    def telegram_webhook(self, bot_id, **kwargs):
        """Handle incoming Telegram webhook requests"""
        try:
            # Get the bot configuration
            bot = request.env['telegram.bot'].sudo().browse(bot_id)
            if not bot.exists() or not bot.active:
                return Response(status=404)

            # Get the update data
            update = json.loads(request.httprequest.data)
            _logger.info(f"Received Telegram update: {update}")

            # Process the message
            if 'message' in update:
                self._process_message(bot, update['message'])
            elif 'callback_query' in update:
                self._process_callback_query(bot, update['callback_query'])

            return {'status': 'ok'}

        except Exception as e:
            _logger.error(f"Error processing webhook: {str(e)}")
            return Response(status=500)

    def _process_message(self, bot, message):
        """Process incoming message"""
        chat_id = message['chat']['id']
        text = message.get('text', '')

        # Store or update chat information
        chat = request.env['telegram.chat'].sudo().search([
            ('chat_id', '=', str(chat_id)),
            ('bot_id', '=', bot.id)
        ], limit=1)

        if not chat:
            chat = request.env['telegram.chat'].sudo().create({
                'chat_id': str(chat_id),
                'username': message['chat'].get('username'),
                'first_name': message['chat'].get('first_name'),
                'last_name': message['chat'].get('last_name'),
                'bot_id': bot.id
            })

        # Handle commands
        if text.startswith('/'):
            self._handle_command(bot, chat, text)
        else:
            self._handle_message(bot, chat, text)

    def _handle_command(self, bot, chat, command):
        """Handle bot commands"""
        if command == '/start':
            welcome_msg = """🤖 Welcome to Odoo Telegram Bot!

Available commands:
/start - Show this message
/help - Show help information
/status - Check system status
"""
            bot.send_message(chat.chat_id, welcome_msg)

        elif command == '/help':
            help_msg = """📋 Help Information:

This bot connects to your Odoo system. You can:
- Receive notifications
- Check order status
- Get reports
- And much more!
"""
            bot.send_message(chat.chat_id, help_msg)

        elif command == '/status':
            # Example: Check system status
            status_msg = "✅ System is online and running smoothly!"
            bot.send_message(chat.chat_id, status_msg)

    def _handle_message(self, bot, chat, text):
        """Handle regular messages"""
        response_msg = f"Received your message: {text}\n\nI'll process it soon!"
        bot.send_message(chat.chat_id, response_msg)

    def _process_callback_query(self, bot, callback_query):
        """Process callback queries from inline keyboards"""
        pass  # Implement callback handling if needed