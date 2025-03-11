/** @odoo-module **/

// import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";

export class PartnerFormController extends FormController {
  async setup() {
    super.setup();
    if (!this.props.resId) {
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
         
          this.model.config.context["partner_longitude"] = longitude;
          this.model.config.context["partner_latitude"] = latitude;
        }
      } else {
        alert("Geolocation is not supported by this browser.");
        console.log("Geolocation is not supported by this browser.");
      }
    }
  }
}
export class SaleOrderFormController extends FormController {
  async setup() {
    super.setup();
    if (!this.props.resId) {
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
       

          this.model.config.context["partner_longitude"] = longitude;
          this.model.config.context["partner_latitude"] = latitude;
        }
      } else {
        alert("Geolocation is not supported by this browser.");

        console.log("Geolocation is not supported by this browser.");
      }
    }
  }
}

export const SaleOrderFormView = {
  ...formView,
  Controller: SaleOrderFormController,
};
export const PartnerFormView = {
  ...formView,
  Controller: PartnerFormController,
};

registry
  .category("views")
  .add("add_lat_long_partner_view_form", PartnerFormView);

registry
  .category("views")
  .add("add_lat_long_sale_order_view_form", SaleOrderFormView);
