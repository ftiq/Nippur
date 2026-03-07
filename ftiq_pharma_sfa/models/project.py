from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    ftiq_plan_ids = fields.One2many('ftiq.weekly.plan', 'project_id', string='FTIQ Plans')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    ftiq_plan_id = fields.Many2one('ftiq.weekly.plan', string='FTIQ Weekly Plan', ondelete='set null', index=True)
    ftiq_plan_line_id = fields.Many2one('ftiq.weekly.plan.line', string='FTIQ Plan Line', ondelete='set null', index=True)
    ftiq_daily_task_id = fields.Many2one('ftiq.daily.task', string='FTIQ Daily Task', ondelete='set null', index=True)
