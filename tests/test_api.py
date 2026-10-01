import json
from pathlib import Path

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from routing.models import FuelStation, ImportRun
from routing.providers.base import NoRouteError, RoutingProviderError, RoutingTimeout
from routing.providers.osrm import meters_to_miles
from routing.services.planner import Planner
from routing.station_index import clear
from routing.views import RouteView

FIXTURE = json.loads(Path("tests/fixtures/osrm_dallas_chicago.json").read_text())


class FakeProvider:
    def __init__(self, error=None):
        self.calls = 0
        self.error = error

    def route(self, start, finish):
        self.calls += 1
        if self.error:
            raise self.error
        r = FIXTURE["routes"][0]
        return {
            "distance_miles": meters_to_miles(r["distance"]),
            "duration_hours": r["duration"] / 3600,
            "geometry": r["geometry"],
            "provider": "fixture",
        }


@pytest.fixture
def api(db):
    coords = FIXTURE["routes"][0]["geometry"]["coordinates"]
    for ident, (lng, lat) in [
        (1001, coords[len(coords) // 3]),
        (1002, coords[len(coords) * 2 // 3]),
    ]:
        FuelStation.objects.create(
            opis_id=ident,
            name="Test Station",
            address="Exit",
            city="Test",
            state="TX",
            latitude=lat,
            longitude=lng,
            price_usd_per_gallon=3.2,
            price_min=3.2,
            price_max=3.2,
        )
    ImportRun.objects.create(data_version="test", source_name="fixture")
    clear()
    cache.clear()
    provider = FakeProvider()
    RouteView.planner_factory = staticmethod(lambda: Planner(provider))
    return APIClient(), provider


def test_normalization():
    from routing.providers.geocode import normalize_city

    assert normalize_city("St. Louis") == normalize_city("Saint Louis")
    assert normalize_city("Mt. Pleasant") == normalize_city("Mount Pleasant")


def test_happy_path_schema_and_external_call(api):
    client, provider = api
    response = client.get("/api/route/", {"start": "Dallas, TX", "finish": "Chicago, IL"})
    body = response.json()
    assert (
        response.status_code == 200
        and {"start", "finish", "route", "vehicle", "fuel_stops", "summary", "assumptions", "meta"}
        <= body.keys()
    )
    assert (
        body["meta"]["external_calls"] == 1
        and body["meta"]["routing_source"] == "provider"
        and provider.calls == 1
    )


def test_identical_request_is_full_cache_hit(api):
    client, provider = api
    client.get("/api/route/", {"start": "Dallas, TX", "finish": "Chicago, IL"})
    second = client.get("/api/route/", {"start": "Dallas, TX", "finish": "Chicago, IL"}).json()
    assert (
        second["meta"]["cache"] == "hit"
        and second["meta"]["osrm_ms"] == 0
        and second["meta"]["external_calls"] == 0
        and second["meta"]["routing_source"] == "cache"
        and provider.calls == 1
    )


def test_vehicle_change_reuses_route_cache(api):
    client, provider = api
    client.get("/api/route/", {"start": "Dallas, TX", "finish": "Chicago, IL", "mpg": 10})
    second = client.get(
        "/api/route/", {"start": "Dallas, TX", "finish": "Chicago, IL", "mpg": 12}
    ).json()
    assert provider.calls == 1 and second["meta"]["osrm_ms"] == 0


def test_missing_non_us_and_bounds_are_400(api):
    client, _ = api
    assert client.get("/api/route/").status_code == 400
    assert (
        client.get("/api/route/", {"start": "Toronto, ON", "finish": "Chicago, IL"}).status_code
        == 400
    )
    assert (
        client.get(
            "/api/route/", {"start": "Dallas, TX", "finish": "Chicago, IL", "mpg": 0}
        ).status_code
        == 400
    )
    assert (
        client.get(
            "/api/route/", {"start": "Dallas, TX", "finish": "Chicago, IL", "range_miles": 5000}
        ).status_code
        == 400
    )


def test_get_post_equivalence(api):
    client, _ = api
    a = client.get("/api/route/", {"start": "Dallas, TX", "finish": "Chicago, IL"}).json()
    cache.clear()
    b = client.post(
        "/api/route/", {"start": "Dallas, TX", "finish": "Chicago, IL"}, format="json"
    ).json()
    assert a["route"] == b["route"] and a["summary"] == b["summary"]


def test_fuel_conservation_and_no_borrowing(api):
    client, _ = api
    body = client.get("/api/route/", {"start": "Dallas, TX", "finish": "Chicago, IL"}).json()
    s = body["summary"]
    stops = body["fuel_stops"]
    assert (
        abs(
            body["vehicle"]["starting_fuel_gallons"]
            + s["gallons_purchased"]
            - s["gallons_consumed"]
            - s["ending_fuel_gallons"]
        )
        < 0.01
    )
    assert s["fuel_paid_at_stations_usd"] == round(sum(x["cost_usd"] for x in stops), 2)
    assert s["total_fuel_cost_usd"] == pytest.approx(
        s["fuel_paid_at_stations_usd"] + s["starting_tank_value_usd"], abs=0.01
    )


def test_no_fuel_gap_names_gap(api):
    client, _ = api
    FuelStation.objects.update(latitude=0, longitude=0)
    clear()
    response = client.get("/api/route/", {"start": "Dallas, TX", "finish": "Chicago, IL"})
    body = response.json()
    assert (
        response.status_code == 422
        and body["error"]["code"] == "NO_FUEL_STATION_IN_RANGE"
        and "gap" in body["error"]["message"].lower()
    )
    assert {
        "gap_start_mile",
        "gap_end_mile",
        "range_miles",
        "min_range_miles_needed",
        "suggestion",
    } <= body["error"]["details"].keys()


def test_no_route_502_504_and_no_stations(api):
    client, _ = api
    for exc, code in [
        (NoRouteError("none"), "NO_ROUTE"),
        (RoutingProviderError("bad"), "ROUTING_PROVIDER_ERROR"),
        (RoutingTimeout("slow"), "ROUTING_PROVIDER_TIMEOUT"),
    ]:
        cache.clear()
        p = FakeProvider(exc)
        RouteView.planner_factory = staticmethod(lambda p=p: Planner(p))
        response = client.get("/api/route/", {"start": "Dallas, TX", "finish": "Chicago, IL"})
        assert response.json()["error"]["code"] == code
        assert response.status_code in (422, 502, 504)
    FuelStation.objects.all().delete()
    clear()
    cache.clear()
    RouteView.planner_factory = staticmethod(lambda: Planner(FakeProvider()))
    response = client.get("/api/route/", {"start": "Dallas, TX", "finish": "Chicago, IL"})
    assert response.status_code == 503


def test_short_trip_has_zero_stops_and_estimate(api):
    client, _ = api
    p = FakeProvider()
    r = FIXTURE["routes"][0]
    r = dict(r)
    r["geometry"] = {"type": "LineString", "coordinates": r["geometry"]["coordinates"][:10]}
    r["distance"] = 16093.44
    p.route = lambda start, finish: {
        "distance_miles": 10.0,
        "duration_hours": 0.2,
        "geometry": r["geometry"],
        "provider": "fixture",
    }
    FuelStation.objects.filter(opis_id=1001).update(
        latitude=FIXTURE["routes"][0]["geometry"]["coordinates"][0][1],
        longitude=FIXTURE["routes"][0]["geometry"]["coordinates"][0][0],
    )
    clear()
    RouteView.planner_factory = staticmethod(lambda: Planner(p))
    body = client.get(
        "/api/route/",
        {"start": "Dallas, TX", "finish": "Chicago, IL", "range_miles": 50, "mpg": 10},
    ).json()
    assert body["summary"]["number_of_stops"] == 0 and body["summary"]["total_fuel_cost_usd"] > 0


def test_cache_miss_does_not_query_after_station_index_warm(api):
    client, _ = api
    from routing.station_index import stations

    stations()
    cache.clear()
    # Endpoint geocoding and station matching are in-memory; the import version is already represented by the test cache.
    response = client.get("/api/route/", {"start": "Dallas, TX", "finish": "Chicago, IL"})
    assert response.status_code == 200


def test_input_normalization_and_route_alias(api):
    client, _ = api
    body = client.get(
        "/api/route/", {"start": "Dallas, Texas", "finish": "Chicago, Illinois"}
    ).json()
    assert body["start"]["resolved"] == "Dallas, TX"
    assert body["finish"]["resolved"] == "Chicago, IL"
    alias = client.get("/api/route", {"start": "Dallas, TX", "finish": "Chicago, IL"})
    assert alias.status_code == 200 and alias["Content-Type"].startswith("application/json")
    same = client.get("/api/route/", {"start": "Dallas,TX", "finish": "Dallas,TX"})
    assert same.status_code == 400
    assert same.json()["error"]["code"] == "INVALID_PARAMS"


def test_unsupported_locations_have_distinct_codes(api):
    client, _ = api
    honolulu = client.get("/api/route/", {"start": "Honolulu, HI", "finish": "Chicago, IL"})
    alaska = client.get("/api/route/", {"start": "Anchorage, AK", "finish": "Chicago, IL"})
    free_text = client.get(
        "/api/route/", {"start": "1600 Pennsylvania Ave NW, Washington DC", "finish": "Dallas, TX"}
    )
    toronto = client.get("/api/route/", {"start": "Toronto, ON", "finish": "Chicago, IL"})
    assert honolulu.json()["error"]["code"] == "LOCATION_NOT_SUPPORTED"
    assert alaska.json()["error"]["code"] == "LOCATION_NOT_SUPPORTED"
    assert free_text.json()["error"]["code"] in {"LOCATION_NOT_SUPPORTED", "LOCATION_NOT_FOUND"}
    assert toronto.json()["error"]["code"] == "LOCATION_NOT_IN_US"
