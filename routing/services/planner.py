"""Build route plans by combining geocoding, routing, stations, and refuelling."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import numpy as np
from django.conf import settings
from django.core.cache import cache

from routing.corridor import match_corridor
from routing.geo import cumulative_miles, densify
from routing.models import ImportRun
from routing.optimizer import Candidate, InfeasibleRoute, plan_refuelling
from routing.providers.geocode import resolve_location
from routing.providers.osrm import default_provider
from routing.station_index import stations


def data_version() -> str:
    """Return the current imported station data version."""
    record = ImportRun.objects.order_by("-created_at").first()
    return record.data_version if record else "empty"


def cache_key(prefix: str, value: dict[str, Any]) -> str:
    """Build a stable cache key for a JSON-compatible value."""
    encoded = json.dumps(value, sort_keys=True).encode()
    return prefix + hashlib.sha256(encoded).hexdigest()


def simplify(coords: list[list[float]], tolerance: float = 0.01) -> list[list[float]]:
    """Reduce route geometry while preserving its first and last coordinates."""
    if len(coords) <= 2:
        return coords
    keep = [0]
    array = np.asarray(coords, float)
    for index in range(1, len(array) - 1):
        if np.linalg.norm(array[index] - array[keep[-1]]) >= tolerance:
            keep.append(index)
    keep.append(len(array) - 1)
    return [coords[index] for index in keep]


class Planner:
    """Coordinate endpoint resolution, route retrieval, station matching, and planning."""

    def __init__(self, provider: Any | None = None) -> None:
        self.provider = provider or default_provider()

    def plan(
        self,
        start_text: str,
        finish_text: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a complete route response for the requested endpoints and vehicle."""
        params = params or {}
        started = time.perf_counter()
        timings: dict[str, float] = {}
        external_calls = [0]

        resolve_started = time.perf_counter()
        start = resolve_location(start_text, external_calls)
        finish = resolve_location(finish_text, external_calls)
        timings["resolve_endpoints_ms"] = round((time.perf_counter() - resolve_started) * 1000, 2)

        if (
            abs(start.point.lat - finish.point.lat) < 1e-9
            and abs(start.point.lng - finish.point.lng) < 1e-9
        ):
            raise ValueError("Start and finish must be different locations")

        range_miles = float(
            params.get("range_miles", getattr(settings, "DEFAULT_RANGE_MILES", 500))
        )
        mpg = float(params.get("mpg", getattr(settings, "DEFAULT_MPG", 10)))
        corridor_miles = float(
            params.get("corridor_miles", getattr(settings, "DEFAULT_CORRIDOR_MILES", 5))
        )
        stop_penalty = float(
            params.get(
                "stop_penalty_usd",
                getattr(settings, "DEFAULT_STOP_PENALTY_USD", 5),
            )
        )
        geometry_mode = params.get("geometry", "simplified")
        starting_fuel = (
            float(params["starting_fuel_gallons"]) if "starting_fuel_gallons" in params else None
        )

        if not 50 <= range_miles <= 1500:
            raise ValueError("Invalid route parameters")
        if not 1 <= mpg <= 50:
            raise ValueError("Invalid route parameters")
        if starting_fuel is None:
            starting_fuel = range_miles / mpg
        if not 0 <= starting_fuel <= range_miles / mpg:
            raise ValueError("Invalid route parameters")
        if not 1 <= corridor_miles <= 15:
            raise ValueError("Invalid route parameters")
        if not 0 <= stop_penalty <= 100:
            raise ValueError("Invalid route parameters")
        if geometry_mode not in {"simplified", "full", "none"}:
            raise ValueError("Invalid route parameters")

        version = data_version()
        full_key = cache_key(
            "route:",
            {
                "s": start_text.casefold().strip(),
                "f": finish_text.casefold().strip(),
                "range": range_miles,
                "mpg": mpg,
                "start_fuel": starting_fuel,
                "corridor": corridor_miles,
                "geometry": geometry_mode,
                "penalty": stop_penalty,
                "version": version,
            },
        )
        cached = cache.get(full_key)
        if cached:
            elapsed = round((time.perf_counter() - started) * 1000, 2)
            cached["meta"].update(
                {
                    "cache": "hit",
                    "external_calls": 0,
                    "routing_source": "cache",
                    "osrm_ms": 0.0,
                    "compute_ms": elapsed,
                    "total_ms": elapsed,
                }
            )
            return cached

        route_key = cache_key(
            "routing:",
            {
                "s": round(start.point.lat, 3),
                "sl": round(start.point.lng, 3),
                "f": round(finish.point.lat, 3),
                "fl": round(finish.point.lng, 3),
            },
        )
        route = cache.get(route_key)
        route_cache_hit = route is not None
        osrm_started = time.perf_counter()
        if route is None:
            route = self.provider.route(start.point, finish.point)
            cache.set(route_key, route, 7 * 86400)
        osrm_ms = 0.0 if route_cache_hit else round((time.perf_counter() - osrm_started) * 1000, 2)

        prep_started = time.perf_counter()
        coords = route["geometry"]["coordinates"]
        raw_lat = np.array([point[1] for point in coords])
        raw_lon = np.array([point[0] for point in coords])
        lat, lon = densify(raw_lat, raw_lon, 1)
        total_miles = route["distance_miles"]
        cumulative = cumulative_miles(lat, lon, total_miles)
        timings["route_prep_ms"] = round((time.perf_counter() - prep_started) * 1000, 2)

        rows = stations()
        if not rows:
            raise LookupError("Fuel data not loaded")

        candidates: list[Candidate] = []
        used_corridor = 0.0
        last_error: InfeasibleRoute | None = None
        corridor_elapsed = 0.0
        optimizer_elapsed = 0.0
        matched_hits = []
        plan = None
        station_lat = np.array([row["latitude"] for row in rows])
        station_lon = np.array([row["longitude"] for row in rows])
        station_ids = np.array([row["opis_id"] for row in rows])
        station_prices = np.array([float(row["price_usd_per_gallon"]) for row in rows])

        for radius in [corridor_miles, 10.0, 15.0]:
            match_started = time.perf_counter()
            hits = match_corridor(
                lat,
                lon,
                cumulative,
                station_lat,
                station_lon,
                station_ids,
                station_prices,
                radius,
            )
            corridor_elapsed += time.perf_counter() - match_started
            candidates = [Candidate(hit.station_id, hit.mile, hit.price) for hit in hits]
            try:
                optimizer_started = time.perf_counter()
                plan = plan_refuelling(
                    candidates,
                    total_miles,
                    range_miles,
                    mpg,
                    starting_fuel,
                    stop_penalty,
                )
                optimizer_elapsed += time.perf_counter() - optimizer_started
                matched_hits = hits
                used_corridor = radius
                break
            except InfeasibleRoute as exc:
                last_error = exc

        timings["corridor_match_ms"] = round(corridor_elapsed * 1000, 2)
        timings["optimizer_ms"] = round(optimizer_elapsed * 1000, 2)
        if plan is None:
            assert last_error is not None
            raise last_error

        build_started = time.perf_counter()
        by_id = {row["opis_id"]: row for row in rows}
        stops = []
        for order, purchase in enumerate(plan.purchases, 1):
            row = by_id[purchase.station_id]
            stops.append(
                {
                    "order": order,
                    "station_id": purchase.station_id,
                    "name": row["name"],
                    "address": row["address"],
                    "city": row["city"],
                    "state": row["state"],
                    "lat": row["latitude"],
                    "lng": row["longitude"],
                    "mile_marker": round(purchase.mile, 2),
                    "distance_from_route_miles": round(
                        next(
                            hit.offset_miles
                            for hit in matched_hits
                            if hit.station_id == purchase.station_id
                        ),
                        2,
                    ),
                    "price_per_gallon_usd": round(purchase.price, 3),
                    "arrival_fuel_gallons": round(purchase.arrival_gallons, 3),
                    "gallons_purchased": round(purchase.gallons, 3),
                    "cost_usd": round(purchase.cost, 2),
                    "reason": purchase.reason,
                }
            )

        paid_at_stations = round(sum(stop["cost_usd"] for stop in stops), 2)
        prices = [hit.price for hit in matched_hits]
        if stops:
            price_basis = round(
                paid_at_stations / sum(stop["gallons_purchased"] for stop in stops), 3
            )
            average_paid = price_basis
            cost_basis = "Total fuel cost includes rounded station purchases and the value of fuel consumed from the starting full tank, priced at the average station purchase price."
        elif prices:
            price_basis = round(float(np.median(prices)), 3)
            average_paid = None
            cost_basis = "No station purchases were needed; total fuel cost is the starting tank fuel consumed, priced at the median corridor station price."
        else:
            price_basis = None
            average_paid = None
            cost_basis = "No station purchases or corridor prices were available, so total fuel cost is unavailable."

        starting_tank_value = (
            round((starting_fuel - plan.ending_gallons) * price_basis, 2)
            if price_basis is not None
            else None
        )
        total_fuel_cost = (
            round(paid_at_stations + starting_tank_value, 2)
            if starting_tank_value is not None
            else None
        )
        if geometry_mode == "none":
            geometry = None
        else:
            geometry = {
                "type": "LineString",
                "coordinates": coords if geometry_mode == "full" else simplify(coords),
            }
        timings["response_build_ms"] = round((time.perf_counter() - build_started) * 1000, 2)
        elapsed = round((time.perf_counter() - started) * 1000, 2)

        response = {
            "start": {
                "input": start_text,
                "resolved": start.resolved,
                "lat": start.point.lat,
                "lng": start.point.lng,
                "source": start.source,
            },
            "finish": {
                "input": finish_text,
                "resolved": finish.resolved,
                "lat": finish.point.lat,
                "lng": finish.point.lng,
                "source": finish.source,
            },
            "summary": {
                "total_fuel_cost_usd": total_fuel_cost,
                "fuel_paid_at_stations_usd": paid_at_stations,
                "starting_tank_value_usd": starting_tank_value,
                "price_basis_per_gallon": price_basis,
                "cost_basis": cost_basis,
                "gallons_purchased": round(plan.gallons_purchased, 3),
                "gallons_consumed": round(plan.gallons_consumed, 3),
                "ending_fuel_gallons": round(plan.ending_gallons, 3),
                "average_price_paid_per_gallon_usd": average_paid,
                "number_of_stops": len(stops),
            },
            "fuel_stops": stops,
            "assumptions": {
                "starting_fuel": "Vehicle starts with a full tank; starting tank value is included in total fuel cost.",
                "price_rule": "median of duplicate CSV rows per station ID",
                "station_locations": "approximate: city centroid",
                "corridor_miles": corridor_miles,
                "corridor_policy": "auto-widens 5 -> 10 -> 15 miles",
                "stop_penalty_usd": stop_penalty,
                "stop_penalty_policy": "heuristic candidate-pruned penalty optimizer for long routes; penalty 0 uses the greedy reference fast path",
                "cost_policy": "total fuel cost equals station purchases plus consumed starting-tank fuel at the price basis",
                "detours": "Stations within the corridor are treated as on-route; detour miles are not charged.",
            },
            "route": {
                "distance_miles": round(total_miles, 2),
                "duration_hours": round(route.get("duration_hours", 0), 2),
                "geometry": geometry,
                "geometry_points": len(geometry["coordinates"]) if geometry else 0,
                "provider": route.get("provider", "osrm"),
            },
            "vehicle": {
                "range_miles": range_miles,
                "mpg": mpg,
                "tank_gallons": range_miles / mpg,
                "starting_fuel_gallons": starting_fuel,
            },
            "map_url": f"/map/?start={start_text}&finish={finish_text}",
            "meta": {
                "external_calls": external_calls[0] + (0 if route_cache_hit else 1),
                "cache": "miss",
                "routing_source": "cache" if route_cache_hit else "provider",
                "osrm_ms": osrm_ms,
                "compute_ms": round(elapsed - osrm_ms, 2),
                "total_ms": elapsed,
                "corridor_miles_used": used_corridor,
                "data_version": version,
                "timings": timings,
            },
        }
        cache.set(full_key, response, 86400)
        return response
