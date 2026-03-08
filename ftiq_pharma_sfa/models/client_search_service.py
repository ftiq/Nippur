import math

from odoo import _, fields, models


class FtiqClientSearchService(models.AbstractModel):
    _name = "ftiq.client.search.service"
    _description = "FTIQ Client Search Service"

    def _get_client_base_domain(self):
        return self.env["ftiq.plan.candidate.service"].get_client_base_domain()

    @staticmethod
    def _distance_km(latitude_1, longitude_1, latitude_2, longitude_2):
        if None in (latitude_1, longitude_1, latitude_2, longitude_2):
            return False
        radius_km = 6371.0
        latitude_1 = math.radians(latitude_1)
        longitude_1 = math.radians(longitude_1)
        latitude_2 = math.radians(latitude_2)
        longitude_2 = math.radians(longitude_2)
        delta_latitude = latitude_2 - latitude_1
        delta_longitude = longitude_2 - longitude_1
        arc = (
            math.sin(delta_latitude / 2.0) ** 2
            + math.cos(latitude_1) * math.cos(latitude_2) * math.sin(delta_longitude / 2.0) ** 2
        )
        return radius_km * (2.0 * math.atan2(math.sqrt(arc), math.sqrt(1.0 - arc)))

    def _serialize_partner(self, partner, latitude=False, longitude=False):
        invoice_domain = [
            ("partner_id", "child_of", partner.commercial_partner_id.id),
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
        ]
        open_invoices = self.env["account.move"].sudo().search(invoice_domain)
        distance_km = False
        if latitude and longitude and partner.partner_latitude and partner.partner_longitude:
            distance_km = self._distance_km(latitude, longitude, partner.partner_latitude, partner.partner_longitude)
        return {
            "id": partner.id,
            "name": partner.display_name,
            "client_code": partner.ftiq_client_code or "",
            "client_type": partner.ftiq_client_type or "client",
            "client_type_label": partner.ftiq_client_type_label or _("Client"),
            "category": partner.ftiq_client_category_id.name or "",
            "specialty": partner.ftiq_specialty_id.name or "",
            "classification": partner.ftiq_classification_id.name or "",
            "address": partner.ftiq_execution_address or "",
            "city": partner.ftiq_city_id.name or partner.city or "",
            "area": partner.ftiq_area_id.name or "",
            "geo_confirmed": bool(partner.ftiq_geo_confirmed),
            "geo_ready": bool(partner.ftiq_geo_ready),
            "latitude": partner.partner_latitude or 0.0,
            "longitude": partner.partner_longitude or 0.0,
            "phone": partner.phone or "",
            "mobile": partner.mobile or "",
            "last_visit_date": str(partner.ftiq_last_visit_date or ""),
            "total_visits": partner.ftiq_total_visits,
            "order_count": partner.ftiq_order_count,
            "collection_count": partner.ftiq_collection_count,
            "invoice_count": partner.ftiq_invoice_count,
            "open_invoice_count": len(open_invoices),
            "open_invoice_amount": sum(open_invoices.mapped("amount_residual")),
            "distance_km": round(distance_km, 2) if distance_km is not False else False,
            "is_nearby": bool(distance_km is not False and distance_km <= 5.0),
            "general_note": partner.ftiq_general_note or "",
        }

    def search_clients(
        self,
        search_term="",
        client_code="",
        country_id=False,
        city_id=False,
        area_id=False,
        latitude=False,
        longitude=False,
        radius_km=0.0,
        limit=25,
    ):
        domain = list(self._get_client_base_domain())
        if search_term:
            domain.extend([
                "|",
                "|",
                "|",
                ("name", "ilike", search_term),
                ("ftiq_client_code", "ilike", search_term),
                ("street", "ilike", search_term),
                ("city", "ilike", search_term),
            ])
        if client_code:
            domain.append(("ftiq_client_code", "ilike", client_code))
        if country_id:
            domain.append(("country_id", "=", country_id))
        if city_id:
            domain.append(("ftiq_city_id", "=", city_id))
        if area_id:
            domain.append(("ftiq_area_id", "=", area_id))
        partners = self.env["res.partner"].search(domain, order="name")
        if latitude and longitude:
            partners = partners.filtered(lambda partner: partner.partner_latitude and partner.partner_longitude)
            partners = partners.sorted(
                key=lambda partner: self._distance_km(
                    latitude,
                    longitude,
                    partner.partner_latitude,
                    partner.partner_longitude,
                )
            )
            if radius_km:
                partners = partners.filtered(
                    lambda partner: self._distance_km(
                        latitude,
                        longitude,
                        partner.partner_latitude,
                        partner.partner_longitude,
                    ) <= radius_km
                )
        partners = partners[:limit]
        return [self._serialize_partner(partner, latitude=latitude, longitude=longitude) for partner in partners]

    def search_nearby_clients(self, latitude, longitude, radius_km=5.0, limit=25):
        return self.search_clients(
            search_term="",
            client_code="",
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            limit=limit,
        )

    def get_client_card(self, partner_id, latitude=False, longitude=False):
        partner = self.env["res.partner"].browse(partner_id).exists()
        if not partner:
            return {}
        data = self._serialize_partner(partner, latitude=latitude, longitude=longitude)
        recent_visits = self.env["ftiq.visit"].sudo().search([
            ("partner_id", "=", partner.id),
        ], order="visit_date desc, id desc", limit=5)
        data["recent_visits"] = [{
            "id": visit.id,
            "name": visit.display_name,
            "date": str(visit.visit_date or ""),
            "state": visit.state,
            "outcome": visit.outcome or "",
        } for visit in recent_visits]
        data["updated_at"] = fields.Datetime.to_string(fields.Datetime.now())
        return data
