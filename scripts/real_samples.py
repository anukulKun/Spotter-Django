"""Regenerate committed sample responses from cached route geometries."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()

from routing.optimizer import InfeasibleRoute
from routing.services.planner import Planner

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "docs" / "sample_responses"
ROUTES = [
    ("dallas_chicago", "Dallas, TX", "Chicago, IL", {}),
    ("newyork_miami", "New York, NY", "Miami, FL", {}),
    ("losangeles_newyork", "Los Angeles, CA", "New York, NY", {}),
    ("seattle_miami", "Seattle, WA", "Miami, FL", {}),
    ("losangeles_seattle_gap", "Los Angeles, CA", "Seattle, WA", {}),
    ("losangeles_seattle_range1000", "Los Angeles, CA", "Seattle, WA", {"range_miles": 1000}),
    ("denver_kansascity", "Denver, CO", "Kansas City, MO", {}),
    ("dallas_fortworth", "Dallas, TX", "Fort Worth, TX", {}),
]


class CachedProvider:
    """Supply a route geometry from the previous committed response."""

    def __init__(self, route: dict):
        self.route_data = route

    def route(self, start, finish):
        return dict(self.route_data)


for name, start, finish, params in ROUTES:
    old = json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8-sig"))
    old_route = old.get("route")
    if not old_route or not old_route.get("geometry"):
        print(f"{name}: retained existing error response")
        continue
    provider = CachedProvider(old_route)
    try:
        body = Planner(provider).plan(start, finish, params)
        status = 200
    except InfeasibleRoute as exc:
        body = {
            "error": {
                "code": "NO_FUEL_STATION_IN_RANGE",
                "message": str(exc),
                "details": {
                    "gap_start_mile": exc.gap_start_mile,
                    "gap_end_mile": exc.gap_end_mile,
                    "range_miles": exc.range_miles,
                    "min_range_miles_needed": exc.min_range_miles_needed,
                    "suggestion": "Increase range_miles or choose a route with more stations.",
                },
            }
        }
        status = 422
    output = {"http_status": status, **body}
    (SAMPLES / f"{name}.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(
        name, status, body.get("route", {}).get("distance_miles"), len(body.get("fuel_stops", []))
    )
