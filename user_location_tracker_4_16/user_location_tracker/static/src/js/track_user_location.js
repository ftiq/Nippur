/** @odoo-module **/

import { onMounted } from "@odoo/owl";

// onMounted(() => {
// alert("🚀 Location Tracker Activated");
// startTracking();
// });

function getCurrentLocation() {
  return new Promise((resolve, reject) => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: true,
      });
    } else {
      reject(new Error("Geolocation is not supported."));
    }
  });
}

// async function sendLocation(latitude, longitude) {
//   alert("sended from js");

//   await fetch("/user_location_tracker/update_location", {
//     method: "POST",
//     headers: {
//       "Content-Type": "application/json",
//       "X-Requested-With": "XMLHttpRequest",
//     },
//     body: JSON.stringify({ latitude, longitude }),
//   })
//     .catch((r) => {
//       alert("request Error ", r);
//     })
//     .finally((f) => {
//       alert("final", f);
//     })
//     .then((t) => {
//       alert("then");
//       alert(t.body);
//     });
// }
async function sendLocation(latitude, longitude) {
  console.log("Sending coordinates:", latitude, longitude); // Add this line

  await fetch("/user_location_tracker/update_location", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
    body: JSON.stringify({ latitude, longitude }),
  })
    .catch((r) => {
      console.error("Request Error:", r); // Update to log to console
    })
    .finally((f) => {
      console.log("Request completed:", f); // Add this line for more clarity
    })
    .then((t) => {
      console.log("Response received:", t); // Add this to check response
    });
}

async function startTracking() {
  try {
    const position = await getCurrentLocation();
    const lat = position.coords.latitude;
    const lon = position.coords.longitude;

    console.log("Latitude:", lat, "Longitude:", lon); // Add this log
    await sendLocation(lat, lon);
  } catch (error) {
    console.error("Error:", error);
    console.warn("❌ Location error:", error);
  }

  setTimeout(startTracking, 15000);
}

document.addEventListener("DOMContentLoaded", () => {
  startTracking();
});
