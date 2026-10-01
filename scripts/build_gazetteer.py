"""Build data/us_cities.csv from the GeoNames US.txt dump."""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
US_CODES = {"AL", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"}


def build(source: Path, destination: Path) -> int:
    places = {}
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            if len(row) < 15 or row[6] != "P" or row[8] != "US" or row[10] not in US_CODES:
                continue
            state, population = row[10], int(row[14] or 0)
            for city in dict.fromkeys((row[1], row[2])):
                if city and ((city, state) not in places or population > places[(city, state)][2]):
                    places[(city, state)] = (row[4], row[5], population)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["city", "state", "lat", "lng", "population"])
        for (city, state), (lat, lng, population) in sorted(places.items()):
            writer.writerow([city, state, lat, lng, population])
    return len(places)


if __name__ == "__main__":
    source = ROOT / "data" / "US.txt"
    destination = ROOT / "data" / "us_cities.csv"
    if not source.exists():
        raise SystemExit(f"Missing {source}. Download GeoNames US.zip, extract US.txt, then rerun.")
    print(f"Wrote {build(source, destination)} gazetteer rows to {destination}")
