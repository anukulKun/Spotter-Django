from __future__ import annotations

import csv
import difflib
import re
import statistics
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from routing.models import FuelStation

US_STATES = {"AL", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"}


def normalize_city(value: str) -> str:
    value = value.casefold().strip()
    value = re.sub(r"\b(st)\.?\b", "saint", value)
    value = re.sub(r"\b(ft)\.?\b", "fort", value)
    value = re.sub(r"\b(mt)\.?\b", "mount", value)
    value = re.sub(r"\\b(twp|township)\\b", "", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def load_gazetteer(path: Path) -> dict[tuple[str, str], tuple[float, float, int]]:
    result = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            city, state = normalize_city(row["city"]), row["state"].strip().upper()
            candidate = (float(row["lat"]), float(row["lng"]), int(float(row.get("population") or 0)))
            key = (city, state)
            if key not in result or candidate[2] > result[key][2]:
                result[key] = candidate
    return result


def resolve_city(city: str, state: str, gazetteer: dict):
    key = (normalize_city(city), state.upper())
    if key in gazetteer:
        lat, lng, _ = gazetteer[key]
        return lat, lng, "city"
    choices = [name for name, st in gazetteer if st == state.upper()]
    match = difflib.get_close_matches(key[0], choices, n=1, cutoff=0.9)
    if match:
        lat, lng, _ = gazetteer[(match[0], state.upper())]
        return lat, lng, "fuzzy"
    return None, None, "unresolved"


class Command(BaseCommand):
    help = "Import and normalize fuel prices, geocoding stations from an offline gazetteer."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=Path)
        parser.add_argument("--gazetteer", type=Path)
        parser.add_argument("--price-rule", choices=("median", "min", "max", "mean"), default="median")

    def handle(self, *args, **options):
        csv_path: Path = options["csv_path"]
        gazetteer_path = options.get("gazetteer")
        if not csv_path.exists():
            raise CommandError(f"CSV not found: {csv_path}")
        gazetteer = {}
        if gazetteer_path:
            if gazetteer_path.exists():
                gazetteer = load_gazetteer(gazetteer_path)
            else:
                self.stdout.write(self.style.WARNING(f"Gazetteer not found: {gazetteer_path}"))
        else:
            self.stdout.write(self.style.WARNING("No gazetteer supplied; stations cannot be geocoded."))

        rows = list(csv.DictReader(csv_path.open(newline="", encoding="utf-8-sig")))
        us_rows = [row for row in rows if row["State"].strip().upper() in US_STATES]
        groups = {}
        for row in us_rows:
            groups.setdefault(int(row["OPIS Truckstop ID"]), []).append(row)
        prices = [[float(row["Retail Price"]) for row in group] for group in groups.values()]
        all_prices = [price for group in prices for price in group]
        median = statistics.median(all_prices)
        deviations = [abs(price - median) for price in all_prices]
        mad = statistics.median(deviations)
        threshold = 5.0
        objects, unresolved = [], []
        for opis_id, group in groups.items():
            values = [float(row["Retail Price"]) for row in group]
            first = group[0]
            if options["price_rule"] == "min": aggregate = min(values)
            elif options["price_rule"] == "max": aggregate = max(values)
            elif options["price_rule"] == "mean": aggregate = statistics.mean(values)
            else: aggregate = statistics.median(values)
            name = max((row["Truckstop Name"].strip() for row in group), key=len)
            city, state = first["City"].strip(), first["State"].strip().upper()
            lat, lng, quality = resolve_city(city, state, gazetteer)
            if quality == "unresolved": unresolved.append(f"{city}, {state}")
            objects.append(FuelStation(
                opis_id=opis_id, name=name, address=first["Address"].strip(), city=city, state=state,
                latitude=lat, longitude=lng, price_usd_per_gallon=Decimal(f"{aggregate:.4f}"),
                price_rows_merged=len(values), price_min=Decimal(f"{min(values):.4f}"),
                price_max=Decimal(f"{max(values):.4f}"), geocode_quality=quality,
                is_price_outlier=aggregate > threshold,
            ))
        with transaction.atomic():
            FuelStation.objects.bulk_create(objects, update_conflicts=True, unique_fields=["opis_id"], update_fields=[
                "name", "address", "city", "state", "latitude", "longitude", "price_usd_per_gallon", "price_rows_merged", "price_min", "price_max", "geocode_quality", "is_price_outlier",
            ])
        city_matches = sum(obj.latitude is not None and obj.geocode_quality == "city" for obj in objects)
        outliers = sum(obj.is_price_outlier for obj in objects)
        self.stdout.write(f"Rows read:                {len(rows)}")
        self.stdout.write(f"Dropped (non-US):          {len(rows) - len(us_rows)}")
        self.stdout.write(f"US rows:                  {len(us_rows)}")
        self.stdout.write(f"Unique stations:          {len(objects)}")
        self.stdout.write(f"IDs with multiple prices: {sum(len(g) > 1 for g in groups.values())}  (rule={options['price_rule']})")
        self.stdout.write(f"Geocoded (city match):    {city_matches}")
        self.stdout.write(f"Unresolved:                {len(unresolved)}   (listed below)")
        self.stdout.write(f"Price outliers flagged:    {outliers}")
        if unresolved:
            self.stdout.write("Unresolved cities: " + ", ".join(sorted(set(unresolved))))
        if not gazetteer_path or not gazetteer:
            self.stdout.write(self.style.WARNING("Obtain GeoNames US.zip, extract US.txt, run scripts\\build_gazetteer.py, then provide data\\us_cities.csv with columns city,state,lat,lng,population; no download was attempted."))
