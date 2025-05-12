import requests
from odoo import models, fields, api

class UserLocationLog(models.Model):
    _name = 'user.location.log'
    _description = 'User Location Log'
    _order = 'create_date desc'

    user_id = fields.Many2one('res.users', string='User', required=True)
    latitude = fields.Float('Latitude', required=True)
    longitude = fields.Float('Longitude', required=True)
    tracked_at = fields.Datetime('Tracked At', default=fields.Datetime.now)
    country_name = fields.Char('Country', readonly=True)
    address = fields.Char('Address', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            location_info = self._get_location_info(vals.get('latitude'), vals.get('longitude'))
            if location_info:
                vals.update(location_info)
        return super().create(vals_list)

    def _get_location_info(self, latitude, longitude):
        try:
            url = f'https://nominatim.openstreetmap.org/reverse?lat={latitude}&lon={longitude}&format=json'
            headers = {
                'User-Agent': 'Odoo Location Tracker Module'
            }
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return {
                    'country_name': data.get('address', {}).get('country', ''),
                    'address': data.get('display_name', '')
                }
        except Exception as e:
            self.env.logger.error(f'Error getting location info: {str(e)}')
        return {}
