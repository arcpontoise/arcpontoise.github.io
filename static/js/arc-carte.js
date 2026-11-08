// Maps of the plan d'accès page, drawn with Leaflet (static/vendor/leaflet)
// from OpenStreetMap raster tiles: no WebGL needed, unlike the embedded
// openstreetmap.org map.
//
// <div class="lieu-carte" data-latitude="49.04532" data-longitude="2.0851"
//   data-titre="Le terrain">fallback content</div>
// Without JavaScript, or if Leaflet is missing, the fallback content stays.

(() => {
  "use strict";

  const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  const ATTRIBUTION =
    '&copy; <a href="https://www.openstreetmap.org/copyright">contributeurs OpenStreetMap</a>';

  function draw(holder) {
    const latitude = Number(holder.dataset.latitude);
    const longitude = Number(holder.dataset.longitude);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return;
    holder.replaceChildren();
    const map = window.L.map(holder, { scrollWheelZoom: false }).setView([latitude, longitude], 16);
    window.L.tileLayer(TILES, { maxZoom: 19, attribution: ATTRIBUTION }).addTo(map);
    window.L.circleMarker([latitude, longitude], {
      radius: 10,
      color: "#1b2b5a",
      weight: 3,
      fillColor: "#3f60aa",
      fillOpacity: 0.9,
    })
      .addTo(map)
      .bindTooltip(holder.dataset.titre || "", { direction: "top", offset: [0, -10] });
  }

  function start() {
    if (!window.L) return;
    document.querySelectorAll(".lieu-carte[data-latitude]").forEach(draw);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
