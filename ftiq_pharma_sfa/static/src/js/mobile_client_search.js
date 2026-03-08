/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class FtiqClientSearch extends Component {
    static template = "ftiq_pharma_sfa.MobileClientSearch";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            query: "",
            clientCode: "",
            radiusKm: 5,
            latitude: false,
            longitude: false,
            nearbyMode: false,
            results: [],
            card: null,
        });
        onWillStart(async () => {
            const defaultPartnerId = this.props.action?.context?.default_partner_id;
            if (defaultPartnerId) {
                await this.loadCard(defaultPartnerId);
            }
            await this.searchClients();
        });
    }

    get card() {
        return this.state.card || {};
    }

    get hasCard() {
        return Boolean(this.card.id);
    }

    async searchClients() {
        this.state.loading = true;
        try {
            const results = await this.orm.call("res.partner", "ftiq_search_clients", [
                this.state.query,
                this.state.clientCode,
                false,
                false,
                false,
                this.state.latitude || false,
                this.state.longitude || false,
                this.state.nearbyMode ? Number(this.state.radiusKm || 0) : 0,
                25,
            ]);
            this.state.results = results || [];
            if (!this.hasCard && this.state.results.length) {
                await this.loadCard(this.state.results[0].id);
            }
        } catch (error) {
            this.notification.add(_t("Unable to search clients."), { type: "danger" });
            throw error;
        } finally {
            this.state.loading = false;
        }
    }

    async loadCard(partnerId) {
        this.state.card = await this.orm.call("res.partner", "ftiq_get_client_card", [
            partnerId,
            this.state.latitude || false,
            this.state.longitude || false,
        ]);
    }

    async useNearbySearch() {
        if (!navigator.geolocation) {
            this.notification.add(_t("Geolocation is not available in this browser."), { type: "warning" });
            return;
        }
        this.state.loading = true;
        try {
            const position = await new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(resolve, reject, {
                    enableHighAccuracy: true,
                    maximumAge: 60000,
                    timeout: 15000,
                });
            });
            this.state.latitude = position.coords.latitude;
            this.state.longitude = position.coords.longitude;
            this.state.nearbyMode = true;
            await this.searchClients();
        } catch (error) {
            this.notification.add(_t("Unable to read the current location."), { type: "warning" });
        } finally {
            this.state.loading = false;
        }
    }

    clearNearbyMode() {
        this.state.nearbyMode = false;
        this.state.latitude = false;
        this.state.longitude = false;
        this.searchClients();
    }

    onQueryInput(ev) {
        this.state.query = ev.target.value;
    }

    onCodeInput(ev) {
        this.state.clientCode = ev.target.value;
    }

    onRadiusInput(ev) {
        this.state.radiusKm = Number(ev.target.value || 5);
    }

    onSearchKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.searchClients();
        }
    }

    openRecord(model, resId) {
        if (!resId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openClient() {
        this.openRecord("res.partner", this.card.id);
    }

    openVisits() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Visits"),
            res_model: "ftiq.visit",
            domain: [["partner_id", "=", this.card.id]],
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    openOrders() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Field Orders"),
            res_model: "sale.order",
            domain: [["partner_id", "=", this.card.id], ["is_field_order", "=", true]],
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    openCollections() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Cash Collections"),
            res_model: "account.payment",
            domain: [["partner_id", "=", this.card.id], ["is_field_collection", "=", true]],
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    openInvoices() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Invoices"),
            res_model: "account.move",
            domain: [["partner_id", "=", this.card.id], ["move_type", "=", "out_invoice"]],
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    formatNumber(value) {
        return Number(value || 0).toLocaleString();
    }

    formatCurrency(value) {
        return Number(value || 0).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    formatDistance(value) {
        if (value === false || value === null || value === undefined) {
            return _t("N/A");
        }
        return `${Number(value).toFixed(2)} km`;
    }
}

registry.category("actions").add("ftiq_pharma_sfa.client_search", FtiqClientSearch);
