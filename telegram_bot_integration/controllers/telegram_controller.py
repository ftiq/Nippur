# -*- coding: utf-8 -*-
import json
import logging
import uuid
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
            welcome_msg = """
            🤖 Welcome to Odoo Telegram Bot!
            
            Available commands:
            /start - Show this message
            /help - Show help information
            /status - Check system status
            /invoice [number] - Get invoice details
            /statement - Get account statement
            /link_account - Link your account
            """
            bot.send_message(chat.chat_id, welcome_msg)
            
        elif command == '/help':
            help_msg = """
            📋 Help Information:
            
            This bot connects to your Odoo system. You can:
            - Receive notifications
            - Check invoice status: /invoice [number]
            - Get account statement: /statement
            - Link your account: /link_account
            - And much more!
            """
            bot.send_message(chat.chat_id, help_msg)
            
        elif command == '/status':
            status_msg = "✅ System is online and running smoothly!"
            bot.send_message(chat.chat_id, status_msg)
            
        elif command.startswith('/invoice'):
            self._handle_invoice_command(bot, chat, command)
            
        elif command == '/statement':
            self._handle_statement_command(bot, chat)
            
        elif command == '/link_account':
            self._handle_link_account_command(bot, chat)
            
        else:
            unknown_msg = "❌ Unknown command. Use /help to see available commands."
            bot.send_message(chat.chat_id, unknown_msg)

    def _handle_message(self, bot, chat, text):
        """Handle regular messages"""
        response_msg = f"Received your message: {text}\n\nI'll process it soon!"
        bot.send_message(chat.chat_id, response_msg)

    def _handle_invoice_command(self, bot, chat, command):
        """Handle invoice information request"""
        try:
            # استخراج رقم الفاتورة من الأمر
            parts = command.split()
            if len(parts) < 2:
                bot.send_message(chat.chat_id, "❌ Please provide invoice number. Usage: /invoice INV-2023-001")
                return
                
            invoice_number = parts[1].strip()
            
            # البحث عن الفاتورة في أودو
            invoice = request.env['account.move'].sudo().search([
                ('name', '=', invoice_number),
                ('state', '=', 'posted')
            ], limit=1)
            
            if not invoice:
                bot.send_message(chat.chat_id, f"❌ Invoice {invoice_number} not found or not posted.")
                return
                
            # التحقق من صلاحية الوصول إذا كان الحساب مرتبطاً
            if chat.partner_id and invoice.partner_id.id != chat.partner_id.id:
                bot.send_message(chat.chat_id, "❌ You don't have permission to view this invoice.")
                return
                
            # إعداد رسالة تفاصيل الفاتورة
            invoice_msg = f"""
            🧾 Invoice Details: {invoice.name}
            
            Date: {invoice.invoice_date}
            Due Date: {invoice.invoice_date_due or 'N/A'}
            Customer: {invoice.partner_id.name}
            Amount: {invoice.amount_total} {invoice.currency_id.name}
            Status: {invoice.state}
            
            Items:
            """
            
            for line in invoice.invoice_line_ids:
                invoice_msg += f"• {line.name}: {line.quantity} x {line.price_unit} = {line.price_subtotal}\n"
                
            invoice_msg += f"\nTotal: {invoice.amount_total} {invoice.currency_id.name}"
            
            bot.send_message(chat.chat_id, invoice_msg)
            
        except Exception as e:
            error_msg = "❌ Error retrieving invoice information. Please try again later."
            bot.send_message(chat.chat_id, error_msg)
            _logger.error(f"Invoice command error: {str(e)}")

    def _handle_statement_command(self, bot, chat):
        """Handle account statement request"""
        try:
            # التحقق إذا كان المحادثة مرتبطة بحساب
            if not chat.partner_id:
                bot.send_message(chat.chat_id, "❌ Please link your account first using /link_account")
                return
                
            # الحصول على كشف حساب العميل
            partner = chat.partner_id
            moves = request.env['account.move'].sudo().search([
                ('partner_id', '=', partner.id),
                ('state', '=', 'posted'),
                ('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund'])
            ], order='invoice_date desc', limit=10)
            
            if not moves:
                bot.send_message(chat.chat_id, "📊 No transactions found for your account.")
                return
                
            # إعداد رسالة كشف الحساب
            statement_msg = f"""
            📊 Account Statement for: {partner.name}
            
            Recent Transactions (last 10):
            """
            
            for move in moves:
                type_emoji = "🧾" if move.move_type in ['out_invoice', 'in_invoice'] else "🔄"
                sign = -1 if move.move_type in ['out_refund', 'in_refund'] else 1
                amount = move.amount_total * sign
                
                statement_msg += f"{type_emoji} {move.name}: {amount} {move.currency_id.name} ({move.invoice_date})\n"
            
            # حساب الرصيد
            total_due = partner.credit - partner.debit
            statement_msg += f"\n💰 Current Balance: {total_due} {partner.currency_id.name}"
            
            bot.send_message(chat.chat_id, statement_msg)
            
        except Exception as e:
            error_msg = "❌ Error retrieving account statement. Please try again later."
            bot.send_message(chat.chat_id, error_msg)
            _logger.error(f"Statement command error: {str(e)}")

    def _handle_link_account_command(self, bot, chat):
        """Handle account linking request"""
        try:
            # إنشاء token فريد لربط الحساب
            token = str(uuid.uuid4())[:8]
            
            # حفظ token مؤقتاً
            request.env['ir.config_parameter'].sudo().set_param(f'telegram.link_token.{token}', chat.chat_id)
            
            # الحصول على عنوان URL الأساسي
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            
            # إرسال تعليمات الربط
            link_msg = f"""
            🔗 Account Linking Instructions:
            
            1. Login to your Odoo account
            2. Go to your profile settings
            3. Enter this code in the Telegram linking section:
            
            🔒 Code: {token}
            
            Or visit this link to automatically link your account:
            {base_url}/telegram/link?token={token}&chat_id={chat.chat_id}
            
            This code will expire in 24 hours.
            """
            
            bot.send_message(chat.chat_id, link_msg)
            
        except Exception as e:
            error_msg = "❌ Error generating link token. Please try again later."
            bot.send_message(chat.chat_id, error_msg)
            _logger.error(f"Link account error: {str(e)}")

    def _process_callback_query(self, bot, callback_query):
        """Process callback queries from inline keyboards"""
        pass

    @http.route('/telegram/link', type='http', auth='user', website=True)
    def telegram_link_account(self, **kwargs):
        """Web page for linking Telegram account with Odoo user"""
        token = kwargs.get('token')
        chat_id = kwargs.get('chat_id')
        
        if not token or not chat_id:
            return "Invalid link parameters"
        
        # التحقق من صحة token
        stored_chat_id = request.env['ir.config_parameter'].sudo().get_param(f'telegram.link_token.{token}')
        
        if stored_chat_id != chat_id:
            return "Invalid or expired link token"
        
        # ربط حساب المستخدم الحالي مع chat_id
        partner = request.env.user.partner_id
        chat = request.env['telegram.chat'].sudo().search([('chat_id', '=', chat_id)], limit=1)
        
        if chat:
            chat.write({
                'partner_id': partner.id,
                'user_id': request.env.user.id
            })
            
            # إرسال رسالة تأكيد عبر التليجرام
            bot = chat.bot_id
            if bot:
                bot.send_message(chat_id, f"✅ Account linked successfully! Welcome {partner.name}")
            
            # مسح token المستخدم
            request.env['ir.config_parameter'].sudo().set_param(f'telegram.link_token.{token}', '')
            
            return "Account linked successfully! You can return to Telegram now."
        
        return "Error linking account"