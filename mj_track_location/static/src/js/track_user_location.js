/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

/**
 * Get the current location using the browser's Geolocation API.
 * @returns {Promise<GeolocationPosition>} A promise that resolves with the user's location.
 */
function getCurrentLocation() {
    return new Promise((resolve, reject) => {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(resolve, reject, {
                enableHighAccuracy: true,
            });
        } else {
            reject(new Error("Geolocation is not supported by this browser."));
        }
    });
}

/**
 * Send the user's location to the server.
 * @param {number} latitude - The latitude to send.
 * @param {number} longitude - The longitude to send.
 */
async function sendLocationToServer(latitude, longitude) {
    try {
        await rpc("/web/dataset/call_kw/location.session/store_user_location", {
            model: 'location.session',
            method: 'store_user_location',
            args: [{'latitude': latitude,'longitude': longitude}],
            kwargs: {},
        }).then(function (result) {
            console.log(result);
        });
        console.log("Location sent to the server successfully.");
    } catch (error) {
        console.log(error);
        console.error("Failed to send location to the server:", error.message);
    }
}

/**
 * Start tracking the user's location and send it to the server every 30 minutes.
 */
async function startLocationTracking() {
    try {
        // Get the user's location
        const position = await getCurrentLocation();
        const latitude = position.coords.latitude;
        const longitude = position.coords.longitude;

        // Send the location to the server
        await sendLocationToServer(latitude, longitude);

        console.log(`Latitude: ${latitude}, Longitude: ${longitude}`);
    } catch (error) {
        console.warn("Error fetching location:", error.message);
    }

    // Schedule the next location update in 30 minutes
    setTimeout(startLocationTracking, 30 * 60 * 1000);
    // setTimeout(startLocationTracking, 20000);
}

// Call the location tracking function on document ready
document.addEventListener("DOMContentLoaded", () => {
    console.log("Document is ready. Starting location tracking...");
    startLocationTracking();
});
