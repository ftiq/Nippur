from odoo import models, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    def write(self, vals):
        # Perform the initial write operation
        res = super(AccountMove, self).write(vals)
        
        # Check if 'date' was updated and no context flag to skip this update
        if 'date' in vals and not self.env.context.get('delay_invoice_date_update'):
            # Update the invoice_date with a context flag to prevent recursion
            self.with_context(delay_invoice_date_update=True).write({
                'invoice_date': self.date
            })
        return res
