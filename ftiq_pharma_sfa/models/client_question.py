from odoo import models, fields


class FtiqClientQuestion(models.Model):
    _name = 'ftiq.client.question'
    _description = 'Client Profile Question'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    question_type = fields.Selection([
        ('selection', 'Selection'),
        ('text', 'Text'),
        ('integer', 'Integer'),
        ('float', 'Float'),
        ('boolean', 'Yes / No'),
    ], required=True, default='text')
    applies_to = fields.Selection([
        ('doctor', 'Doctor'),
        ('center', 'Center'),
        ('both', 'Both'),
    ], required=True, default='both')
    required = fields.Boolean(default=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    option_ids = fields.One2many('ftiq.client.question.option', 'question_id')


class FtiqClientQuestionOption(models.Model):
    _name = 'ftiq.client.question.option'
    _description = 'Question Option'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    question_id = fields.Many2one('ftiq.client.question', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)


class FtiqClientAnswer(models.Model):
    _name = 'ftiq.client.answer'
    _description = 'Client Answer'
    _order = 'question_id'

    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade')
    question_id = fields.Many2one('ftiq.client.question', required=True, ondelete='cascade')
    option_id = fields.Many2one('ftiq.client.question.option', ondelete='set null')
    text_value = fields.Char()
    integer_value = fields.Integer()
    float_value = fields.Float()
    boolean_value = fields.Boolean()
    note = fields.Text()

    _sql_constraints = [
        ('partner_question_uniq', 'unique(partner_id, question_id)',
         'Only one answer per question per client is allowed.'),
    ]
