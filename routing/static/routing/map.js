(() => {
  "use strict";

  const query = new URLSearchParams(window.location.search);
  const form = document.getElementById("route-form");
  const errorElement = document.getElementById("error");
  const summaryElement = document.getElementById("summary");
  const stopsBody = document.querySelector("#stops tbody");
  const assumptionsElement = document.getElementById("assumptions");
  const timingsElement = document.getElementById("timings");
  const rawJsonLink = document.getElementById("raw-json");
  const fallbackNote = document.getElementById("fallback-note");
  let routeLayer = null;
  let markers = [];
  let fallbackUsed = false;
  let tileFailures = 0;

  ["start", "finish", "range_miles", "mpg", "stop_penalty_usd"].forEach((name) => {
    if (query.has(name)) document.getElementById(name).value = query.get(name);
  });

  const map = L.map("map").setView([39, -98], 4);
  const osmLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 19
  });
  osmLayer.on("tileerror", () => {
    tileFailures += 1;
    if (tileFailures >= 5 && !fallbackUsed) {
      fallbackUsed = true;
      map.removeLayer(osmLayer);
      L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
        attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
        maxZoom: 20,
        subdomains: "abcd"
      }).addTo(map);
      fallbackNote.hidden = false;
    }
  });
  osmLayer.addTo(map);

  function clearError() {
    errorElement.hidden = true;
    errorElement.querySelector("strong").textContent = "";
  }

  function showError(error) {
    errorElement.querySelector("strong").textContent = error.message || "The route could not be loaded.";
    if (error.details && error.details.suggestion) {
      errorElement.querySelector("strong").textContent += " " + error.details.suggestion;
    }
    errorElement.hidden = false;
  }

  function money(value) {
    return value === null || value === undefined ? "-" : "$" + Number(value).toFixed(2);
  }

  function markerIcon(kind, label) {
    const colors = { start: "#27855b", stop: "#e36c32", finish: "#b74747" };
    const size = kind === "stop" ? 26 : 22;
    return L.divIcon({
      className: "",
      html: '<span style="display:block;width:' + size + 'px;height:' + size + 'px;border-radius:50%;background:' + colors[kind] + ';border:2px solid white;color:white;text-align:center;line-height:' + (size - 4) + 'px;font-weight:bold">' + (label || "") + "</span>",
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2]
    });
  }

  function stopPopup(stop) {
    return "<strong>" + stop.name + "</strong><br>" +
      stop.city + ", " + stop.state + "<br>" +
      money(stop.price_per_gallon_usd) + "/gal, " + stop.gallons_purchased + " gal, " +
      money(stop.cost_usd) + "<br>Mile marker " + stop.mile_marker;
  }

  function clearMapOverlays() {
    markers.forEach((marker) => map.removeLayer(marker));
    markers = [];
    if (routeLayer) {
      map.removeLayer(routeLayer);
      routeLayer = null;
    }
  }

  function renderBody(body) {
    const summary = body.summary;
    summaryElement.innerHTML = [
      "<li>Distance: " + body.route.distance_miles + " miles</li>",
      "<li>Number of stops: " + summary.number_of_stops + "</li>",
      "<li>Gallons used: " + summary.gallons_consumed + "</li>",
      "<li>Total fuel cost: " + money(summary.total_fuel_cost_usd) + "</li>",
      "<li>Fuel paid at stations: " + money(summary.fuel_paid_at_stations_usd) + "</li>",
      "<li>Average price per gallon: " + money(summary.average_price_paid_per_gallon_usd) + "</li>"
    ].join("");

    const meta = body.meta || {};
    timingsElement.textContent = (meta.routing_source === "cache" ? "Cache hit" : "Routing API") +
      ", server compute " + Number(meta.compute_ms || 0).toFixed(0) + " ms, routing API " +
      Number(meta.osrm_ms || 0).toFixed(0) + " ms";

    assumptionsElement.innerHTML = Object.entries(body.assumptions || {})
      .map(([key, value]) => "<li>" + key.replaceAll("_", " ") + ": " + value + "</li>")
      .join("");

    stopsBody.innerHTML = "";
    (body.fuel_stops || []).forEach((stop, index) => {
      const row = document.createElement("tr");
      [index + 1, stop.name, stop.city + ", " + stop.state, stop.mile_marker,
        Number(stop.price_per_gallon_usd).toFixed(3), stop.gallons_purchased, money(stop.cost_usd)]
        .forEach((value) => {
          const cell = document.createElement("td");
          cell.textContent = value;
          row.appendChild(cell);
        });
      stopsBody.appendChild(row);
    });
    if (!body.fuel_stops || body.fuel_stops.length === 0) {
      stopsBody.innerHTML = "<tr><td colspan='7'>No fuel stops needed.</td></tr>";
    }

    clearMapOverlays();
    if (body.route.geometry) {
      routeLayer = L.geoJSON(body.route.geometry).addTo(map);
      map.invalidateSize();
      map.fitBounds(routeLayer.getBounds(), { padding: [30, 30] });
    }

    const start = L.marker([body.start.lat, body.start.lng], { icon: markerIcon("start", "") })
      .bindPopup("Start").addTo(map);
    const finish = L.marker([body.finish.lat, body.finish.lng], { icon: markerIcon("finish", "") })
      .bindPopup("Finish").addTo(map);
    markers.push(start, finish);

    (body.fuel_stops || []).forEach((stop, index) => {
      const marker = L.marker([stop.lat, stop.lng], { icon: markerIcon("stop", index + 1) })
        .bindPopup(stopPopup(stop)).addTo(map);
      markers.push(marker);
    });

    rawJsonLink.href = "/api/route/?" + new URLSearchParams(new FormData(form)).toString();
  }

  async function loadRoute() {
    clearError();
    const params = new URLSearchParams(new FormData(form));
    for (const [key, value] of [...params]) if (!value) params.delete(key);
    const url = "/api/route/?" + params.toString();
    rawJsonLink.href = url;
    history.replaceState(null, "", "/map/?" + params.toString());
    try {
      const response = await fetch(url, { headers: { Accept: "application/json" } });
      const body = await response.json();
      if (!response.ok) {
        showError(body.error || {});
        return;
      }
      renderBody(body);
    } catch (error) {
      showError({ message: "The route request failed. Check that the server is running." });
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    loadRoute();
  });
  loadRoute();
})();
