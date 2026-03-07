/** @odoo-module */

import { loadCSS, loadJS } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillUpdateProps, useRef, useState } from "@odoo/owl";

const LEAFLET_CSS = "/ftiq_pharma_sfa/static/lib/leaflet/leaflet.css";
const LEAFLET_JS = "/ftiq_pharma_sfa/static/lib/leaflet/leaflet.js";
const LEAFLET_DRAW_CSS = "/ftiq_pharma_sfa/static/lib/leaflet_draw/leaflet.draw.css";
const LEAFLET_DRAW_JS = "/ftiq_pharma_sfa/static/lib/leaflet_draw/leaflet.draw.js";
const LEAFLET_MARKERCLUSTER_CSS = "/ftiq_pharma_sfa/static/lib/leaflet_markercluster/MarkerCluster.css";
const LEAFLET_MARKERCLUSTER_DEFAULT_CSS = "/ftiq_pharma_sfa/static/lib/leaflet_markercluster/MarkerCluster.Default.css";
const LEAFLET_MARKERCLUSTER_JS = "/ftiq_pharma_sfa/static/lib/leaflet_markercluster/leaflet.markercluster.js";

let geoMapLibrariesPromise;

function loadGeoMapLibraries() {
    if (!geoMapLibrariesPromise) {
        geoMapLibrariesPromise = Promise.all([
            loadCSS(LEAFLET_CSS),
            loadCSS(LEAFLET_DRAW_CSS),
            loadCSS(LEAFLET_MARKERCLUSTER_CSS),
            loadCSS(LEAFLET_MARKERCLUSTER_DEFAULT_CSS),
        ])
            .then(() => loadJS(LEAFLET_JS))
            .then(() => loadJS(LEAFLET_DRAW_JS))
            .then(() => loadJS(LEAFLET_MARKERCLUSTER_JS));
    }
    return geoMapLibrariesPromise;
}

function areCoordinatesEqual(firstPoint, secondPoint) {
    return (
        Math.abs(firstPoint[0] - secondPoint[0]) < 1e-7 &&
        Math.abs(firstPoint[1] - secondPoint[1]) < 1e-7
    );
}

function normalizePolygon(rawPolygon) {
    if (!rawPolygon) {
        return [];
    }
    let parsedPolygon;
    try {
        parsedPolygon = JSON.parse(rawPolygon);
    } catch {
        return [];
    }
    let points = [];
    if (parsedPolygon && parsedPolygon.type === "Polygon" && Array.isArray(parsedPolygon.coordinates)) {
        points = parsedPolygon.coordinates[0] || [];
    } else if (Array.isArray(parsedPolygon)) {
        points = parsedPolygon;
    }
    const normalizedPoints = points
        .filter((point) => Array.isArray(point) && point.length >= 2)
        .map((point) => [Number(point[0]), Number(point[1])])
        .filter((point) => Number.isFinite(point[0]) && Number.isFinite(point[1]));
    if (
        normalizedPoints.length > 1 &&
        areCoordinatesEqual(normalizedPoints[0], normalizedPoints[normalizedPoints.length - 1])
    ) {
        normalizedPoints.pop();
    }
    return normalizedPoints.length >= 3 ? normalizedPoints : [];
}

function serializePolygon(points) {
    const closedPoints = [...points];
    if (
        closedPoints.length &&
        !areCoordinatesEqual(closedPoints[0], closedPoints[closedPoints.length - 1])
    ) {
        closedPoints.push(closedPoints[0]);
    }
    return JSON.stringify({
        type: "Polygon",
        coordinates: [closedPoints],
    });
}

function pointInPolygon(point, polygonPoints) {
    const [longitude, latitude] = point;
    let inside = false;
    let previousIndex = polygonPoints.length - 1;
    polygonPoints.forEach(([currentLongitude, currentLatitude], index) => {
        const [previousLongitude, previousLatitude] = polygonPoints[previousIndex];
        const latitudeCrossed = (currentLatitude > latitude) !== (previousLatitude > latitude);
        if (latitudeCrossed) {
            const edgeLatitudeDelta = previousLatitude - currentLatitude || 1e-12;
            const edgeLongitude =
                ((previousLongitude - currentLongitude) * (latitude - currentLatitude)) /
                    edgeLatitudeDelta +
                currentLongitude;
            if (longitude < edgeLongitude) {
                inside = !inside;
            }
        }
        previousIndex = index;
    });
    return inside;
}

function escapeHtml(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function buildPopupContent(marker) {
    const metaParts = [marker.category, marker.specialty, marker.classification].filter(Boolean);
    const addressParts = [marker.area, marker.city, marker.address].filter(Boolean);
    const statusLabel = marker.geo_confirmed ? _t("Geo Confirmed") : _t("Geo Pending");
    return `
        <div class="ftiq_geo_popup">
            <div class="ftiq_geo_popup_name">${escapeHtml(marker.name)}</div>
            ${metaParts.length ? `<div class="ftiq_geo_popup_meta">${escapeHtml(metaParts.join(" - "))}</div>` : ""}
            ${addressParts.length ? `<div class="ftiq_geo_popup_address">${escapeHtml(addressParts.join(" - "))}</div>` : ""}
            <div class="ftiq_geo_popup_status">${escapeHtml(statusLabel)}</div>
        </div>
    `;
}

function buildClientIcon(clientType) {
    const typeClass = clientType || "client";
    return window.L.divIcon({
        className: "ftiq_geo_marker",
        html: `<span class="ftiq_geo_marker_pin ftiq_geo_marker_${typeClass}"></span>`,
        iconSize: [18, 18],
        iconAnchor: [9, 9],
        popupAnchor: [0, -10],
    });
}

export class FtiqPlanGeoMapField extends Component {
    static template = "ftiq_pharma_sfa.PlanGeoMapField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.mapRef = useRef("map");
        this.searchRef = useRef("search");
        this.state = useState({
            loading: true,
            markerCount: 0,
            matchedCount: 0,
            activeTool: "",
        });
        this.map = null;
        this.drawnItems = null;
        this.clusterLayer = null;
        this.polygonDrawHandler = null;
        this.editHandler = null;
        this.partnerMarkers = [];
        this.lastPolygonRaw = "";
        this.markerData = [];

        onMounted(async () => {
            await this.initialize();
        });

        onWillUpdateProps((nextProps) => {
            this.syncPolygonFromRecord(nextProps.record);
        });
    }

    async initialize() {
        try {
            await loadGeoMapLibraries();
            this.markerData = await this.orm.call("ftiq.plan.wizard", "get_geo_partner_markers", []);
            this.state.markerCount = this.markerData.length;
            this.createMap();
            this.renderPartnerMarkers();
            this.syncPolygonFromRecord(this.props.record);
            this.fitMap();
        } catch (error) {
            console.error(error);
            this.notification.add(_t("Unable to initialize the GEO map."), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    createMap() {
        const L = window.L;
        this.map = L.map(this.mapRef.el, {
            scrollWheelZoom: true,
            zoomControl: true,
            preferCanvas: true,
        });
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: "&copy; OpenStreetMap",
        }).addTo(this.map);
        this.drawnItems = L.featureGroup().addTo(this.map);
        this.clusterLayer = L.markerClusterGroup({
            chunkedLoading: true,
            showCoverageOnHover: false,
            spiderfyOnMaxZoom: true,
            maxClusterRadius: 42,
        });
        this.map.addLayer(this.clusterLayer);
        this.polygonDrawHandler = new L.Draw.Polygon(this.map, {
            allowIntersection: false,
            showArea: true,
            shapeOptions: {
                color: "#16a34a",
                weight: 3,
                fillColor: "#22c55e",
                fillOpacity: 0.18,
            },
        });
        this.editHandler = new L.EditToolbar.Edit(this.map, {
            featureGroup: this.drawnItems,
            selectedPathOptions: {
                dashArray: "6 4",
                fill: true,
                fillColor: "#22c55e",
                fillOpacity: 0.22,
                maintainColor: true,
            },
        });
        this.map.on(window.L.Draw.Event.CREATED, (event) => {
            this.drawnItems.clearLayers();
            this.drawnItems.addLayer(event.layer);
            this.persistLayer(event.layer);
            this.resetTools();
        });
        this.map.on(window.L.Draw.Event.EDITED, (event) => {
            event.layers.eachLayer((layer) => this.persistLayer(layer));
        });
        this.map.on(window.L.Draw.Event.EDITVERTEX, () => {
            const currentLayer = this.drawnItems.getLayers()[0];
            if (currentLayer) {
                this.persistLayer(currentLayer, false);
            }
        });
        this.map.on(window.L.Draw.Event.EDITSTOP, () => {
            this.resetTools();
        });
        setTimeout(() => this.map.invalidateSize(), 150);
    }

    renderPartnerMarkers() {
        if (!this.clusterLayer) {
            return;
        }
        this.clusterLayer.clearLayers();
        this.partnerMarkers = this.markerData.map((markerData) => {
            const marker = window.L.marker([markerData.latitude, markerData.longitude], {
                icon: buildClientIcon(markerData.client_type),
            });
            marker.partnerData = markerData;
            marker.bindPopup(buildPopupContent(markerData));
            this.clusterLayer.addLayer(marker);
            return marker;
        });
    }

    fitMap() {
        if (!this.map) {
            return;
        }
        this.map.invalidateSize();
        if (this.drawnItems && this.drawnItems.getLayers().length) {
            this.map.fitBounds(this.drawnItems.getBounds().pad(0.12));
            return;
        }
        if (this.clusterLayer && this.clusterLayer.getLayers().length) {
            const bounds = this.clusterLayer.getBounds();
            if (bounds.isValid()) {
                this.map.fitBounds(bounds.pad(0.12));
                return;
            }
        }
        this.map.setView([20, 0], 2);
    }

    get hasPolygon() {
        return Boolean(this.drawnItems && this.drawnItems.getLayers().length);
    }

    get hasMarkers() {
        return this.state.markerCount > 0;
    }

    getFooterText() {
        if (this.state.loading) {
            return _t("Loading map data...");
        }
        if (!this.hasMarkers) {
            return _t("No geo-enabled clients are available. Add coordinates to client records to use GEO selection.");
        }
        if (!this.hasPolygon) {
            return _t("Use Draw to define a closed search area on the map.");
        }
        return _t("Press Next to review the matching clients inside the selected area.");
    }

    formatCounter(value) {
        return new Intl.NumberFormat().format(value || 0);
    }

    safeUpdate(values) {
        const allowedValues = {};
        const recordData = this.props.record?.data || {};
        for (const [key, value] of Object.entries(values)) {
            if (Object.prototype.hasOwnProperty.call(recordData, key)) {
                allowedValues[key] = value;
            }
        }
        if (Object.keys(allowedValues).length) {
            this.props.record.update(allowedValues);
        }
    }

    getPolygonPointsFromLayer(layer) {
        let latLngs = layer.getLatLngs();
        if (Array.isArray(latLngs[0])) {
            latLngs = latLngs[0];
        }
        return latLngs.map((latLng) => [Number(latLng.lng.toFixed(7)), Number(latLng.lat.toFixed(7))]);
    }

    updateMatchedCount(polygonPoints) {
        if (!polygonPoints.length) {
            this.state.matchedCount = 0;
            return;
        }
        this.state.matchedCount = this.markerData.filter((marker) =>
            pointInPolygon([marker.longitude, marker.latitude], polygonPoints)
        ).length;
    }

    persistLayer(layer, shouldFitMap = true) {
        const polygonPoints = this.getPolygonPointsFromLayer(layer);
        if (polygonPoints.length < 3) {
            this.clearPolygon();
            return;
        }
        const serializedPolygon = serializePolygon(polygonPoints);
        this.lastPolygonRaw = serializedPolygon;
        this.updateMatchedCount(polygonPoints);
        this.safeUpdate({
            geo_polygon: serializedPolygon,
            geo_client_count: this.state.matchedCount,
        });
        if (shouldFitMap) {
            this.fitMap();
        }
    }

    drawPolygon(polygonPoints) {
        if (!this.drawnItems) {
            return;
        }
        this.drawnItems.clearLayers();
        if (polygonPoints.length < 3) {
            this.state.matchedCount = 0;
            return;
        }
        const leafletPolygon = window.L.polygon(
            polygonPoints.map(([longitude, latitude]) => [latitude, longitude]),
            {
                color: "#16a34a",
                weight: 3,
                fillColor: "#22c55e",
                fillOpacity: 0.18,
            }
        );
        this.drawnItems.addLayer(leafletPolygon);
        this.updateMatchedCount(polygonPoints);
    }

    syncPolygonFromRecord(record) {
        const currentPolygonRaw = record?.data?.geo_polygon || "";
        if (currentPolygonRaw === this.lastPolygonRaw) {
            return;
        }
        this.lastPolygonRaw = currentPolygonRaw;
        const polygonPoints = normalizePolygon(currentPolygonRaw);
        this.drawPolygon(polygonPoints);
        if (!polygonPoints.length) {
            this.safeUpdate({ geo_client_count: 0 });
        }
        if (this.map) {
            this.fitMap();
        }
    }

    resetTools() {
        this.state.activeTool = "";
        if (this.polygonDrawHandler?.enabled()) {
            this.polygonDrawHandler.disable();
        }
        if (this.editHandler?.enabled()) {
            this.editHandler.disable();
        }
    }

    startDraw() {
        if (!this.map) {
            return;
        }
        if (this.state.activeTool === "draw") {
            this.resetTools();
            return;
        }
        this.resetTools();
        this.state.activeTool = "draw";
        this.polygonDrawHandler.enable();
    }

    startEdit() {
        if (!this.hasPolygon) {
            this.notification.add(_t("Draw an area first."), { type: "warning" });
            return;
        }
        if (this.state.activeTool === "edit") {
            this.saveEdit();
            return;
        }
        this.resetTools();
        this.state.activeTool = "edit";
        this.editHandler.enable();
    }

    saveEdit() {
        if (!this.editHandler?.enabled()) {
            return;
        }
        this.editHandler.save();
        this.editHandler.disable();
        this.resetTools();
    }

    cancelEdit() {
        if (!this.editHandler?.enabled()) {
            return;
        }
        this.editHandler.revertLayers();
        this.editHandler.disable();
        this.resetTools();
        const currentLayer = this.drawnItems.getLayers()[0];
        if (currentLayer) {
            this.persistLayer(currentLayer);
        } else {
            this.syncPolygonFromRecord(this.props.record);
        }
    }

    clearPolygon() {
        this.resetTools();
        if (this.drawnItems) {
            this.drawnItems.clearLayers();
        }
        this.lastPolygonRaw = "";
        this.state.matchedCount = 0;
        this.safeUpdate({
            geo_polygon: "",
            geo_client_count: 0,
        });
        this.fitMap();
    }

    async searchLocation() {
        const query = this.searchRef.el?.value?.trim();
        if (!query) {
            return;
        }
        try {
            const response = await fetch(
                `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1`
            );
            const results = await response.json();
            const firstResult = results?.[0];
            if (!firstResult) {
                this.notification.add(_t("No location matched the search query."), { type: "warning" });
                return;
            }
            this.map.setView([parseFloat(firstResult.lat), parseFloat(firstResult.lon)], 14);
        } catch {
            this.notification.add(_t("Location search is currently unavailable."), { type: "danger" });
        }
    }

    onSearchKeydown(event) {
        if (event.key === "Enter") {
            event.preventDefault();
            this.searchLocation();
        }
    }

    locateMe() {
        if (!navigator.geolocation) {
            this.notification.add(_t("Geolocation is not supported by this browser."), { type: "warning" });
            return;
        }
        navigator.geolocation.getCurrentPosition(
            (position) => {
                this.map.setView([position.coords.latitude, position.coords.longitude], 14);
            },
            () => {
                this.notification.add(_t("Unable to get the current location."), { type: "danger" });
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0,
            }
        );
    }
}

export const ftiqPlanGeoMapField = {
    component: FtiqPlanGeoMapField,
    supportedTypes: ["char"],
};

registry.category("fields").add("ftiq_geo_plan_map", ftiqPlanGeoMapField);
