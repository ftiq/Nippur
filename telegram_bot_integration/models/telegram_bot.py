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