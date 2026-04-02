import json

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class FtiqPlanCandidateService(models.AbstractModel):
    _name = "ftiq.plan.candidate.service"
    _description = "FTIQ Plan Candidate Service"

    def get_client_base_domain(self):
        return [
            "|",
            "|",
            "|",
            ("is_ftiq_doctor", "=", True),
            ("is_ftiq_center", "=", True),
            ("is_ftiq_pharmacy", "=", True),
            ("ftiq_client_category_id", "!=", False),
        ]

    def build_filter_domain(self, wizard):
        wizard.ensure_one()
        domain = list(self.get_client_base_domain())
        if wizard.filter_partner_id:
            domain.append(("id", "=", wizard.filter_partner_id.id))
        if wizard.filter_name:
            domain.extend([
                "|",
                "|",
                ("name", "ilike", wizard.filter_name),
                ("ftiq_client_code", "ilike", wizard.filter_name),
                ("street", "ilike", wizard.filter_name),
            ])
        if wizard.filter_client_code:
            domain.append(("ftiq_client_code", "ilike", wizard.filter_client_code))
        if wizard.filter_country_id:
            domain.append(("country_id", "=", wizard.filter_country_id.id))
        if wizard.filter_city_id:
            domain.append(("ftiq_city_id", "=", wizard.filter_city_id.id))
        if wizard.filter_area_id:
            domain.append(("ftiq_area_id", "=", wizard.filter_area_id.id))
        if wizard.filter_address:
            domain.append(("street", "ilike", wizard.filter_address))
        if wizard.filter_client_category_id:
            domain.append(("ftiq_client_category_id", "=", wizard.filter_client_category_id.id))
        if wizard.filter_specialty_id:
            domain.append(("ftiq_specialty_id", "=", wizard.filter_specialty_id.id))
        if wizard.filter_subspecialty_id:
            domain.append(("ftiq_subspecialty_id", "=", wizard.filter_subspecialty_id.id))
        if wizard.filter_classification_id:
            domain.append(("ftiq_classification_id", "=", wizard.filter_classification_id.id))
        if wizard.filter_geo_confirmed:
            domain.append(("ftiq_geo_confirmed", "=", True))
        if wizard.filter_app_verified:
            domain.append(("ftiq_app_verified", "=", True))
        if wizard.filter_license_attached:
            domain.append(("ftiq_license_attached", "=", True))
        return domain

    def build_geo_domain(self, polygon_points=None):
        domain = list(self.get_client_base_domain())
        domain.extend([
            ("partner_latitude", "!=", False),
            ("partner_longitude", "!=", False),
        ])
        if polygon_points:
            longitudes = [point[0] for point in polygon_points]
            latitudes = [point[1] for point in polygon_points]
            domain.extend([
                ("partner_longitude", ">=", min(longitudes)),
                ("partner_longitude", "<=", max(longitudes)),
                ("partner_latitude", ">=", min(latitudes)),
                ("partner_latitude", "<=", max(latitudes)),
            ])
        return domain

    def post_filter_partners(self, wizard, partners):
        wizard.ensure_one()
        payment_model = self.env["account.payment"]
        task_model = self.env["ftiq.daily.task"]
        if wizard.filter_has_cashed in ("yes", "no"):
            paid_partners = payment_model.search([
                ("is_field_collection", "=", True),
                ("partner_id", "in", partners.ids),
                ("state", "in", ("in_process", "paid")),
            ]).mapped("partner_id")
            partners = partners & paid_partners if wizard.filter_has_cashed == "yes" else partners - paid_partners
        if wizard.filter_has_tasks in ("yes", "no"):
            task_partners = task_model.search([
                ("partner_id", "in", partners.ids),
                ("state", "!=", "cancelled"),
            ]).mapped("partner_id")
            partners = partners & task_partners if wizard.filter_has_tasks == "yes" else partners - task_partners
        return partners

    @staticmethod
    def normalize_geo_polygon(raw_polygon):
        if not raw_polygon:
            return []
        try:
            polygon = json.loads(raw_polygon)
        except (TypeError, ValueError):
            return []
        points = []
        if isinstance(polygon, dict):
            coordinates = polygon.get("coordinates") or []
            if polygon.get("type") == "Polygon" and coordinates:
                points = coordinates[0]
        elif isinstance(polygon, list):
            points = polygon
        normalized = []
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            try:
                longitude = float(point[0])
                latitude = float(point[1])
            except (TypeError, ValueError):
                continue
            normalized.append((longitude, latitude))
        if len(normalized) > 1 and normalized[0] == normalized[-1]:
            normalized = normalized[:-1]
        return normalized if len(normalized) >= 3 else []

    @staticmethod
    def point_in_polygon(longitude, latitude, polygon_points):
        inside = False
        previous_index = len(polygon_points) - 1
        for index, (current_longitude, current_latitude) in enumerate(polygon_points):
            previous_longitude, previous_latitude = polygon_points[previous_index]
            latitude_crossed = (current_latitude > latitude) != (previous_latitude > latitude)
            if latitude_crossed:
                edge_latitude_delta = previous_latitude - current_latitude or 1e-12
                edge_longitude = (
                    (previous_longitude - current_longitude) * (latitude - current_latitude) / edge_latitude_delta
                ) + current_longitude
                if longitude < edge_longitude:
                    inside = not inside
            previous_index = index
        return inside

    def _score_partner(self, wizard, partner):
        wizard.ensure_one()
        partner.ensure_one()
        score = 0
        if partner.ftiq_geo_confirmed:
            score += 30
        if partner.ftiq_app_verified:
            score += 20
        if partner.ftiq_license_attached:
            score += 10
        if partner.ftiq_last_visit_date:
            score += 5
        if wizard.filter_area_id and partner.ftiq_area_id == wizard.filter_area_id:
            score += 5
        if wizard.filter_specialty_id and partner.ftiq_specialty_id == wizard.filter_specialty_id:
            score += 5
        return score

    def _sort_partners(self, wizard, partners):
        wizard.ensure_one()
        return partners.sorted(
            key=lambda partner: (-self._score_partner(wizard, partner), partner.display_name or "", partner.id)
        )

    def get_filtered_partners(self, wizard):
        wizard.ensure_one()
        partners = self.env["res.partner"].search(self.build_filter_domain(wizard), order="name")
        partners = self.post_filter_partners(wizard, partners)
        return self._sort_partners(wizard, partners)

    def get_geo_partners(self, wizard):
        wizard.ensure_one()
        polygon_points = self.normalize_geo_polygon(wizard.geo_polygon)
        if not polygon_points:
            raise ValidationError(_("Draw an area on the map before continuing."))
        candidate_partners = self.env["res.partner"].search(
            self.build_geo_domain(polygon_points),
            order="name",
        )
        partners = candidate_partners.filtered(
            lambda partner: self.point_in_polygon(
                partner.partner_longitude,
                partner.partner_latitude,
                polygon_points,
            )
        )
        if not partners:
            raise ValidationError(_("No clients were found inside the selected area."))
        return self._sort_partners(wizard, partners)

    def get_matching_partners(self, wizard):
        wizard.ensure_one()
        return self.get_geo_partners(wizard) if wizard.selection_mode == "geo" else self.get_filtered_partners(wizard)

    def get_geo_partner_markers(self):
        partners = self.env["res.partner"].search(self.build_geo_domain(), order="name")
        markers = []
        for partner in partners:
            address_parts = [
                partner.street,
                partner.ftiq_area_id.name,
                partner.ftiq_city_id.name,
                partner.country_id.name,
            ]
            markers.append({
                "id": partner.id,
                "name": partner.name,
                "latitude": partner.partner_latitude,
                "longitude": partner.partner_longitude,
                "client_type": partner.ftiq_client_type or "client",
                "category": partner.ftiq_client_category_id.name or "",
                "specialty": partner.ftiq_specialty_id.name or "",
                "classification": partner.ftiq_classification_id.name or "",
                "address": ", ".join(part for part in address_parts if part),
                "area": partner.ftiq_area_id.name or "",
                "city": partner.ftiq_city_id.name or partner.city or "",
                "geo_confirmed": bool(partner.ftiq_geo_confirmed),
            })
        return markers
