/** @odoo-module **/

// import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";

export class LocationSessionFormController extends FormController {
    async setup() {
        super.setup();
        if(!this.props.resId){
            let latitude = 0;
            let longitude = 0;
            if (navigator.geolocation) {
                const position = await new Promise((resolve, reject) => {
                    navigator.geolocation.getCurrentPosition(resolve, reject);
                }).catch((error) => {
                    console.warn("Geolocation error:", error.message);
                });

                if (position) {
                    latitude = position.coords.latitude;
                    longitude = position.coords.longitude;
                    this.model.config.context['longitude']=longitude;
                    this.model.config.context['latitude']=latitude;
                }
            } else {
                console.log("Geolocation is not supported by this browser.");
            }
        }
    }
}

export const LocationSessionFormView = {
    ...formView,
    Controller: LocationSessionFormController,
};

registry.category("views").add("add_lat_long_location_session_view_form", LocationSessionFormView);

