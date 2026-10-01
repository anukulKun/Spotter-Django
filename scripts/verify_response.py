"""Independently verify a saved route response against station data."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

TOLERANCE = 0.01
DATA_PATH = Path(__file__).parents[1] / "data" / "stations_geocoded.csv"


def report(name: str, passed: bool, detail: str = "") -> bool:
    """Print one check result and return its status."""
    print(f"{'PASS' if passed else 'FAIL'} {name}" + (f": {detail}" if detail else ""))
    return passed


def main(path: str) -> int:
    """Run all independent checks for one saved response JSON."""
    body = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    with DATA_PATH.open(newline="", encoding="utf-8-sig") as handle:
        stations = {int(row["opis_id"]): row for row in csv.DictReader(handle)}

    passed = True
    route = body["route"]
    vehicle = body["vehicle"]
    summary = body["summary"]
    stops = sorted(body.get("fuel_stops", []), key=lambda stop: stop["mile_marker"])
    distance = float(route["distance_miles"])
    range_miles = float(vehicle["range_miles"])
    mpg = float(vehicle["mpg"])
    tank = float(vehicle["tank_gallons"])
    fuel = float(vehicle["starting_fuel_gallons"])
    previous_mile = 0.0

    sorted_ok = all(
        stops[index]["mile_marker"] <= stops[index + 1]["mile_marker"]
        for index in range(len(stops) - 1)
    )
    passed &= report("stops sorted by mile_marker", sorted_ok)

    for stop in stops:
        mile = float(stop["mile_marker"])
        if mile - previous_mile > range_miles + TOLERANCE:
            passed &= report("range gaps", False, f"{previous_mile} -> {mile}")
        station = stations.get(int(stop["station_id"]))
        station_ok = station is not None
        passed &= report("station exists", station_ok, str(stop["station_id"]))
        if station:
            price_ok = (
                abs(float(station["price"]) - float(stop["price_per_gallon_usd"])) <= TOLERANCE
            )
            passed &= report("station price", price_ok, str(stop["station_id"]))
        corridor_ok = (
            float(stop["distance_from_route_miles"])
            <= float(body["meta"]["corridor_miles_used"]) + TOLERANCE
        )
        passed &= report("corridor distance", corridor_ok, str(stop["station_id"]))
        passed &= report("tank before stop", -TOLERANCE <= fuel <= tank + TOLERANCE)
        fuel -= (mile - previous_mile) / mpg
        fuel += float(stop["gallons_purchased"])
        passed &= report("tank after stop", -TOLERANCE <= fuel <= tank + TOLERANCE)
        previous_mile = mile

    passed &= report("final range gap", distance - previous_mile <= range_miles + TOLERANCE)
    fuel -= (distance - previous_mile) / mpg
    passed &= report("tank at finish", -TOLERANCE <= fuel <= tank + TOLERANCE)

    purchased = sum(float(stop["gallons_purchased"]) for stop in stops)
    consumed = float(summary["gallons_consumed"])
    ending = float(summary["ending_fuel_gallons"])
    conservation_ok = (
        abs(float(vehicle["starting_fuel_gallons"]) + purchased - consumed - ending) <= TOLERANCE
    )
    passed &= report("fuel conservation", conservation_ok)

    station_paid = round(sum(round(float(stop["cost_usd"]), 2) for stop in stops), 2)
    if "fuel_paid_at_stations_usd" not in summary:
        passed &= report("fuel paid at stations", False, "field missing")
        print("FAIL one or more checks")
        return 1
    paid_ok = abs(float(summary["fuel_paid_at_stations_usd"]) - station_paid) <= TOLERANCE
    passed &= report("fuel paid at stations", paid_ok)

    basis = summary.get("price_basis_per_gallon")
    if basis is None:
        total_ok = summary.get("total_fuel_cost_usd") is None
    else:
        expected_starting = round(
            (float(vehicle["starting_fuel_gallons"]) - ending) * float(basis), 2
        )
        expected_total = round(station_paid + expected_starting, 2)
        total_ok = (
            abs(float(summary["starting_tank_value_usd"]) - expected_starting) <= TOLERANCE
            and abs(float(summary["total_fuel_cost_usd"]) - expected_total) <= TOLERANCE
        )
    passed &= report("headline total fuel cost", total_ok)
    print("PASS all checks" if passed else "FAIL one or more checks")
    return 0 if passed else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/verify_response.py response.json")
    raise SystemExit(main(sys.argv[1]))
