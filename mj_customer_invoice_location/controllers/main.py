import functools

from odoo import _
from odoo.http import request
from odoo.http import Controller, route, request


class ImportModule(Controller):

    @route('/sale/lang_lat/information',
           type='json', auth='public', methods=['POST'])
    def get_map_info(self, sale_id):
        sale_order = request.env['sale.order'].search(
            [('id', '=', sale_id)], limit=1)
        data = {}
        if sale_order:
            data = {
                'name': sale_order.name,
                'lang': sale_order.partner_latitude,
                'lat': sale_order.partner_longitude
            }
            return data
        else:
            return data

    @route('/partner/lang_lat/information',
           type='json', auth='public', methods=['POST'])
    def get_partner_location(self, partner_id):
        partner = request.env['res.partner'].sudo().search(
            [('id', '=', partner_id)], limit=1)
        data = {}
        if partner:
            data = {
                'name': partner.name,
                'lat': partner.partner_latitude,
                'lng': partner.partner_longitude
            }
        return data
