/** @odoo-module **/

// import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";

export class SaleOrderFormController extends FormController {
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
                    this.model.config.context['partner_longitude']=longitude;
                    this.model.config.context['partner_latitude']=latitude;
                }
            } else {
                console.log("Geolocation is not supported by this browser.");
            }
            // console.log(this.model.config.context);
            // // Wait for the DOM to be ready
            // setTimeout(() => {
            //     const longitudeInput = document.getElementById('partner_longitude_0');
            //     const latitudeInput=document.getElementById('partner_latitude_0');
            //     if (longitudeInput) {
            //         longitudeInput.value = longitude;
            //         latitudeInput.value=latitude;
            //         console.log('Longitude value updated to:', longitudeInput.value);
            //         console.log('Latitude value updated to:', latitudeInput.value);
            //     } else {
            //         console.warn('Element with ID "Longitude" not found.');
            //         console.warn('Element with ID "Latitude" not found.');
            //     }
            // }, 3000); // Delay execution to allow DOM to render
        }
    }
}

export const SaleOrderFormView = {
    ...formView,
    Controller: SaleOrderFormController,
};

registry.category("views").add("add_lat_long_sale_order_view_form", SaleOrderFormView);

