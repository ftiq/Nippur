/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

const GEO_METHODS = ["action_check_in", "action_check_out", "action_start"];

function getGeolocation() {
    return new Promise((resolve) => {
        if (!navigator.geolocation) {
            resolve({ latitude: 0, longitude: 0 });
            return;
        }
        navigator.geolocation.getCurrentPosition(
            (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
            () => resolve({ latitude: 0, longitude: 0 }),
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    });
}

patch(FormController.prototype, {
    async beforeExecuteActionButton(clickParams) {
        if (
            clickParams.type === "object" &&
            GEO_METHODS.includes(clickParams.name)
        ) {
            const coords = await getGeolocation();
            if (!clickParams.buttonContext) {
                clickParams.buttonContext = {};
            }
            clickParams.buttonContext.ftiq_latitude = coords.latitude;
            clickParams.buttonContext.ftiq_longitude = coords.longitude;
        }
        return super.beforeExecuteActionButton(clickParams);
    },
});
