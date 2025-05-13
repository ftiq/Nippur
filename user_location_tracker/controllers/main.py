import json
from odoo import http
from odoo.http import request


class UserLocationTracker(http.Controller):

    @http.route('/user_location_tracker/update_location', type='json', auth='user')
    def update_location(self, **kwargs):
        # Parse the raw body data as JSON
        try:
            body = request.httprequest.get_data(as_text=True)
            data = json.loads(body)
            latitude = data.get('latitude')
            longitude = data.get('longitude')
        except Exception as e:
            return {"error": f"Error parsing JSON: {str(e)}"}

        # Check if latitude and longitude are missing
        if not latitude or not longitude:
            return {"error": f"Missing coordinates. Received: {data}"}

        try:

            request.env['user.location.log'].sudo().create({
                'user_id': request.env.user.id,
                'latitude': latitude,
                'longitude': longitude,
            })

            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
