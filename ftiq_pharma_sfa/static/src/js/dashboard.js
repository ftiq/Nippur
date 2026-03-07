/** @odoo-module */

import { cookie } from "@web/core/browser/cookie";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

class FtiqDashboard extends Component {
    static template = "ftiq_pharma_sfa.Dashboard";
    static props = ["*"];

    setup() {
        this.action = useService("action");
        this.state = useState({
            data: null,
            loading: true,
        });
        onWillStart(async () => {
            await this.loadData();
        });
    }

    get data() {
        return this.state.data || {};
    }

    get isDarkMode() {
        return cookie.get("color_scheme") === "dark";
    }

    async loadData() {
        this.state.loading = true;
        this.state.data = await rpc("/ftiq_pharma_sfa/dashboard_data", {});
        this.state.loading = false;
    }

    async onRefresh() {
        await this.loadData();
    }

    openWindowAction({ name, resModel, domain = [], context = {}, views = [[false, "list"], [false, "form"]] }) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: resModel,
            domain,
            context,
            views,
            target: "current",
        });
    }

    normalizeDomain(extraDomain) {
        return Array.isArray(extraDomain) ? extraDomain : [];
    }

    scopedDomain(fieldName, extraDomain = []) {
        const scopeUserIds = this.data.scope_user_ids || [];
        const scoped = scopeUserIds.length ? [[fieldName, "in", scopeUserIds]] : [];
        return [...scoped, ...this.normalizeDomain(extraDomain)];
    }

    openVisits(extraDomain = []) {
        this.openWindowAction({
            name: _t("Visits"),
            resModel: "ftiq.visit",
            domain: this.scopedDomain("user_id", extraDomain),
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
        });
    }

    openOrders(extraDomain = []) {
        extraDomain = this.normalizeDomain(extraDomain);
        this.openWindowAction({
            name: _t("Field Orders"),
            resModel: "sale.order",
            domain: this.scopedDomain("user_id", [["is_field_order", "=", true], ...extraDomain]),
            views: [[false, "list"], [false, "form"], [false, "kanban"]],
        });
    }

    openCollections(extraDomain = []) {
        extraDomain = this.normalizeDomain(extraDomain);
        this.openWindowAction({
            name: _t("Cash Collections"),
            resModel: "account.payment",
            domain: this.scopedDomain("ftiq_user_id", [["is_field_collection", "=", true], ...extraDomain]),
            context: {
                default_is_field_collection: true,
                default_payment_type: "inbound",
                default_partner_type: "customer",
            },
            views: [[false, "list"], [false, "form"], [false, "kanban"]],
        });
    }

    openTasks(extraDomain = []) {
        this.openWindowAction({
            name: _t("Daily Tasks"),
            resModel: "ftiq.daily.task",
            domain: this.scopedDomain("user_id", extraDomain),
            views: [[false, "kanban"], [false, "list"], [false, "form"], [false, "calendar"]],
        });
    }

    openAttendance(extraDomain = []) {
        this.openWindowAction({
            name: _t("Attendance"),
            resModel: "ftiq.field.attendance",
            domain: this.scopedDomain("user_id", extraDomain),
            views: [[false, "list"], [false, "form"]],
        });
    }

    openStockChecks(extraDomain = []) {
        this.openWindowAction({
            name: _t("Stock Checks"),
            resModel: "ftiq.stock.check",
            domain: this.scopedDomain("user_id", extraDomain),
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
        });
    }

    openInvoices(extraDomain = []) {
        extraDomain = this.normalizeDomain(extraDomain);
        this.openWindowAction({
            name: _t("Open Invoices"),
            resModel: "account.move",
            domain: this.scopedDomain("invoice_user_id", [["move_type", "=", "out_invoice"], ...extraDomain]),
            context: { default_move_type: "out_invoice" },
            views: [[false, "list"], [false, "form"], [false, "kanban"]],
        });
    }

    openTargets(extraDomain = []) {
        this.openWindowAction({
            name: _t("Sales Targets"),
            resModel: "ftiq.sales.target",
            domain: this.scopedDomain("user_id", extraDomain),
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
        });
    }

    openPlanLines(extraDomain = []) {
        this.openWindowAction({
            name: _t("Plan Compliance Report"),
            resModel: "ftiq.weekly.plan.line",
            domain: this.scopedDomain("user_id", extraDomain),
            views: [[false, "pivot"], [false, "list"]],
        });
    }

    openPlanCompliance() {
        this.openPlanLines([
            ["scheduled_date", ">=", this.data.month_start],
            ["scheduled_date", "<=", this.data.month_end],
        ]);
    }

    openMissedPlanLines() {
        this.openPlanLines([
            ["scheduled_date", ">=", this.data.month_start],
            ["scheduled_date", "<=", this.data.month_end],
            ["state", "=", "missed"],
        ]);
    }

    openCheckedInAttendance() {
        this.openAttendance([
            ["date", "=", this.data.date_label],
            ["state", "=", "checked_in"],
        ]);
    }

    openVisit(visitId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "ftiq.visit",
            res_id: visitId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openTarget(targetId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "ftiq.sales.target",
            res_id: targetId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openUserVisits(userId) {
        this.openVisits([
            ["user_id", "=", userId],
            ["visit_date", ">=", this.data.month_start],
            ["visit_date", "<=", this.data.month_end],
        ]);
    }

    openAreaVisits(areaId) {
        const areaDomain = areaId ? [["partner_area_id", "=", areaId]] : [["partner_area_id", "=", false]];
        this.openVisits([
            ...areaDomain,
            ["visit_date", ">=", this.data.month_start],
            ["visit_date", "<=", this.data.month_end],
        ]);
    }

    openPendingApprovals() {
        this.openVisits([["state", "=", "submitted"]]);
    }

    openOverdueTasks() {
        this.openTasks([
            ["state", "not in", ["completed", "cancelled"]],
            ["scheduled_date", "<", this.data.current_datetime],
        ]);
    }

    openAlert(actionKey) {
        const handlers = {
            pending_approvals: () => this.openPendingApprovals(),
            missed_plan_lines: () => this.openMissedPlanLines(),
            overdue_tasks: () => this.openOverdueTasks(),
            active_checkins: () => this.openCheckedInAttendance(),
        };
        const handler = handlers[actionKey];
        if (handler) {
            handler();
        } else {
            this.openPlanCompliance();
        }
    }

    getRoleLabel(role) {
        const labels = {
            manager: _t("Manager View"),
            supervisor: _t("Supervisor View"),
            rep: _t("Representative View"),
        };
        return labels[role] || role;
    }

    getTargetTypeLabel(type) {
        const labels = {
            visits: _t("Visits"),
            orders: _t("Orders"),
            collections: _t("Collections"),
            new_clients: _t("New Clients"),
            products: _t("Products"),
        };
        return labels[type] || type;
    }

    getStateLabel(state) {
        const labels = {
            draft: _t("Draft"),
            in_progress: _t("In Progress"),
            submitted: _t("Submitted"),
            approved: _t("Approved"),
            returned: _t("Returned"),
            pending: _t("Pending"),
            completed: _t("Completed"),
            cancelled: _t("Cancelled"),
        };
        return labels[state] || state;
    }

    getStateBadgeClass(state) {
        const classes = {
            draft: "text-bg-secondary",
            in_progress: "text-bg-info",
            submitted: "text-bg-warning",
            approved: "text-bg-success",
            returned: "text-bg-danger",
            pending: "text-bg-secondary",
            completed: "text-bg-success",
            cancelled: "text-bg-dark",
        };
        return classes[state] || "text-bg-secondary";
    }

    getTaskTypeLabel(type) {
        const labels = {
            visit: _t("Visit"),
            order: _t("Order"),
            delivery: _t("Delivery"),
            collection: _t("Collection"),
            stock: _t("Stock"),
            report: _t("Report"),
            other: _t("Other"),
        };
        return labels[type] || type;
    }

    getToneClass(tone) {
        const classes = {
            primary: "ftiq-tone-primary",
            warning: "ftiq-tone-warning",
            info: "ftiq-tone-info",
            danger: "ftiq-tone-danger",
            success: "ftiq-tone-success",
        };
        return classes[tone] || "ftiq-tone-primary";
    }

    getPresenceLabel(isCheckedIn) {
        return isCheckedIn ? _t("Checked In") : _t("Offline");
    }

    getAreaName(areaName) {
        return areaName || _t("No area assigned");
    }

    formatCurrency(amount) {
        const symbol = this.data.currency_symbol || "";
        return `${Number(amount || 0).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        })} ${symbol}`.trim();
    }

    formatNumber(value) {
        return Number(value || 0).toLocaleString();
    }

    formatPercent(value) {
        return `${Number(value || 0).toFixed(1)}%`;
    }

    formatDuration(value) {
        return `${Number(value || 0).toFixed(1)} h`;
    }
}

registry.category("actions").add("ftiq_pharma_sfa.dashboard", FtiqDashboard);
