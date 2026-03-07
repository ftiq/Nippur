from odoo import models, fields


class FtiqSpecialty(models.Model):
    _name = 'ftiq.specialty'
    _description = 'Medical Specialty'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    subspecialty_ids = fields.One2many('ftiq.subspecialty', 'specialty_id')


class FtiqSubspecialty(models.Model):
    _name = 'ftiq.subspecialty'
    _description = 'Medical Subspecialty'
    _order = 'name'

    name = fields.Char(required=True)
    specialty_id = fields.Many2one('ftiq.specialty', required=True, ondelete='cascade')
    active = fields.Boolean(default=True)


class FtiqClientClassification(models.Model):
    _name = 'ftiq.client.classification'
    _description = 'Client Classification'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class FtiqPrescriberStatus(models.Model):
    _name = 'ftiq.prescriber.status'
    _description = 'Prescriber Status'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)


class FtiqOfficialType(models.Model):
    _name = 'ftiq.official.type'
    _description = 'Official Type'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)


class FtiqSpeakerLevel(models.Model):
    _name = 'ftiq.speaker.level'
    _description = 'Speaker Level'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)


class FtiqLeadershipLevel(models.Model):
    _name = 'ftiq.leadership.level'
    _description = 'Leadership Level'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)


class FtiqWorkplaceType(models.Model):
    _name = 'ftiq.workplace.type'
    _description = 'Workplace Type'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)


class FtiqDebtClassification(models.Model):
    _name = 'ftiq.debt.classification'
    _description = 'Debt Classification'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)


class FtiqColorCode(models.Model):
    _name = 'ftiq.color.code'
    _description = 'Color Code'
    _order = 'name'

    name = fields.Char(required=True)
    color = fields.Integer()
    active = fields.Boolean(default=True)


class FtiqCity(models.Model):
    _name = 'ftiq.city'
    _description = 'City'
    _order = 'name'

    name = fields.Char(required=True)
    country_id = fields.Many2one('res.country')
    state_id = fields.Many2one('res.country.state')
    active = fields.Boolean(default=True)


class FtiqArea(models.Model):
    _name = 'ftiq.area'
    _description = 'Geographic Area'
    _order = 'name'

    name = fields.Char(required=True)
    city_id = fields.Many2one('ftiq.city')
    active = fields.Boolean(default=True)


class FtiqCallReason(models.Model):
    _name = 'ftiq.call.reason'
    _description = 'Call Reason'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class FtiqTaskType(models.Model):
    _name = 'ftiq.task.type'
    _description = 'Task Type'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
