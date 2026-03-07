/** @odoo-module */

import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

const GEO_METHODS_BY_MODEL = {
    "ftiq.field.attendance": ["action_check_out"],
    "ftiq.visit": ["action_start", "action_end"],
    "ftiq.stock.check": ["action_submit"],
    "account.payment": ["action_ftiq_collect", "action_post"],
    "sale.order": ["action_confirm"],
};

function detectMockLocation(coords) {
    if (!coords) {
        return true;
    }
    if (coords.mocked === true) {
        return true;
    }
    if (!Number.isFinite(coords.latitude) || !Number.isFinite(coords.longitude)) {
        return true;
    }
    if (coords.latitude === 0 && coords.longitude === 0) {
        return true;
    }
    return false;
}

function needsGeolocation(controller, clickParams) {
    const resModel = controller.props.resModel;
    const modelMethods = GEO_METHODS_BY_MODEL[resModel] || [];
    if (clickParams.type !== "object" || !modelMethods.includes(clickParams.name)) {
        return false;
    }
    const rootData = controller.model?.root?.data || {};
    if (resModel === "account.payment") {
        return Boolean(rootData.is_field_collection);
    }
    if (resModel === "sale.order") {
        return Boolean(rootData.is_field_order);
    }
    return true;
}

function isAppleMobile() {
    const agent = navigator.userAgent || "";
    return /iPhone|iPad|iPod/i.test(agent);
}

function isAndroid() {
    return /Android/i.test(navigator.userAgent || "");
}

async function getPermissionState() {
    if (!navigator.permissions?.query) {
        return "unknown";
    }
    try {
        const status = await navigator.permissions.query({ name: "geolocation" });
        return status.state || "unknown";
    } catch {
        return "unknown";
    }
}

function buildLocationMessage(permissionState, code) {
    if (!window.isSecureContext) {
        return _t("Location access only works from a secure origin such as HTTPS or localhost. Reload this page from a secure address and try again.");
    }
    const lines = [];
    if (permissionState === "denied" || code === 1) {
        lines.push(_t("Location access is currently blocked for this browser tab."));
        if (isAppleMobile()) {
            lines.push(_t("Turn on Location Services on the device and allow this website to use your location, then tap Retry."));
        } else if (isAndroid()) {
            lines.push(_t("Turn on device Location and allow this site to access location in the browser settings, then tap Retry."));
        } else {
            lines.push(_t("Allow location access for this website in your browser settings, then tap Retry."));
        }
    } else if (code === 2) {
        lines.push(_t("The browser could not determine your current position."));
        lines.push(_t("Turn on GPS or device location services, keep network access enabled, and try again."));
    } else if (code === 3) {
        lines.push(_t("The location request took too long."));
        lines.push(_t("Stay on this page, wait a moment for the GPS signal, and tap Retry."));
    } else {
        lines.push(_t("Location access is required for this action."));
        lines.push(_t("Enable location services for this device and this website, then tap Retry."));
    }
    return lines.join("\n\n");
}

function openLocationDialog(controller, permissionState, code) {
    return new Promise((resolve) => {
        controller.env.services.dialog.add(ConfirmationDialog, {
            title: _t("Location Required"),
            body: buildLocationMessage(permissionState, code),
            confirmLabel: _t("Retry"),
            confirmClass: "btn-primary",
            cancelLabel: _t("Cancel"),
            confirm: () => resolve(true),
            cancel: () => resolve(false),
            dismiss: () => resolve(false),
        });
    });
}

function requestCurrentPosition() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            const error = new Error(_t("Geolocation is not supported by this browser. Use a browser with GPS support."));
            error.code = 0;
            reject(error);
            return;
        }
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const c = pos.coords;
                const isMock = detectMockLocation(c);
                resolve({
                    latitude: c.latitude,
                    longitude: c.longitude,
                    accuracy: c.accuracy || 0,
                    is_mock: isMock,
                });
            },
            (err) => {
                if (err.code === 1) {
                    reject(err);
                } else if (err.code === 2) {
                    reject(err);
                } else {
                    reject(err);
                }
            },
            { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
        );
    });
}

async function getGeolocation(controller, attempt = 0) {
    const permissionState = await getPermissionState();
    try {
        return await requestCurrentPosition();
    } catch (error) {
        const shouldRetry = await openLocationDialog(controller, permissionState, error.code || 0);
        if (shouldRetry && attempt < 2) {
            return getGeolocation(controller, attempt + 1);
        }
        const handledError = new Error(_t("Location request was not completed."));
        handledError.handled = true;
        throw handledError;
    }
}

patch(FormController.prototype, {
    async beforeExecuteActionButton(clickParams) {
        if (needsGeolocation(this, clickParams)) {
            try {
                const coords = await getGeolocation(this);
                if (!clickParams.buttonContext) {
                    clickParams.buttonContext = {};
                }
                clickParams.buttonContext.ftiq_latitude = coords.latitude;
                clickParams.buttonContext.ftiq_longitude = coords.longitude;
                clickParams.buttonContext.ftiq_accuracy = coords.accuracy;
                clickParams.buttonContext.ftiq_is_mock = coords.is_mock;
            } catch (e) {
                if (e.handled) {
                    return;
                }
                this.env.services.notification.add(e.message || _t("Location is required for this action."), {
                    title: "Location Required",
                    type: "danger",
                    sticky: true,
                });
                return;
            }
        }
        return super.beforeExecuteActionButton(clickParams);
    },
});
