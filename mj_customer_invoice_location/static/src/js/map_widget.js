/** @odoo-module */

import { registry } from "@web/core/registry";
import { useRef, Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
// import { jsonrpc } from "@web/core/network/rpc_service";
import { session } from '@web/session';
import { rpc } from "@web/core/network/rpc";
class ChangeLine extends Component { }
ChangeLine.template = "account.ResequenceChangeLine";
ChangeLine.props = ["changeLine", "ordering"];

class MapItem extends Component {

    setup() {
        this.mapRef = useRef("map");
        console.log("hello>>>>>>>>>>>>>>>>>>>>>>>>");
    }
    // async getValue() {
    //     this.sale_data =await jsonrpc("/sale/lang_lat/information", {sale_id:this.props.record.resId});
    //     if (this.sale_data) {
    //         var timer = this.formatProgress(this.task_data);
    //         $(this.task_progress_kanban_ref.el).html(timer);
    //         setInterval(() => {
    //             for (const key in this.task_data) {
    //                 this.task_data[key].progress= this.task_data[key].progress  - 1;
    //             }
    //             timer = this.formatProgress(this.task_data);
    //             $(this.task_progress_kanban_ref.el).html(timer);
    //         }, 1000);
    //     }
    // }
    async getValue() {
        // Fetch the location data from the server
        console.log("hello>>>>>>>>>>>>>>>>>>>>>>>>");
        const response = await rpc("/sale/lang_lat/information", {
            sale_id: this.props.record.resId,
        });
        console.log(response);
        if(response){
            this.set_map_format(response);
        }
    }

    set_map_format(response) {
        // Initialize the map
        console.log(response);
        const map = L.map(this.mapRef.el).setView([response['lang'], response['lat']], 13);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
        }).addTo(map);

        // Add a draggable marker
        const marker = L.marker([response['lang'], response['lat']], { draggable: true }).addTo(map);

        marker.on("dragend", (event) => {
            const position = marker.getLatLng();
            console.log("New Position:", position.lat, position.lng);
            // Optionally, update the value in the backend
        });
    }
}
MapItem.template = "mj_customer_invoice_location.MapWidget"
registry.category("fields").add("custom_map_widget", {
    component: MapItem,
});
