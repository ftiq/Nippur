from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    extract_in_invoice_digitalization_mode = fields.Selection(
        [('no_extract', 'No Extraction')],
        string='Vendor Bills Digitalization',
        default='no_extract',
        help="Temporary field to prevent errors when account_invoice_extract is not installed"
    )
    extract_out_invoice_digitalization_mode = fields.Selection(
        [('no_extract', 'No Extraction')],
        string='Customer Invoices Digitalization', 
        default='no_extract',
        help="Temporary field to prevent errors when account_invoice_extract is not installed"
    )
    extract_single_line_per_tax = fields.Boolean(
        string="Single Line Per Tax",
        help="Temporary field to prevent errors when account_invoice_extract is not installed"
    )
