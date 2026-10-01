from __future__ import annotations

import csv
import difflib
import hashlib
import re
import statistics
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from routing.models import FuelStation, ImportRun

US_STATES = {
    "AL",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
}


def normalize_city(v):
    v = v.casefold().strip()
    v = re.sub(r"\b(st)\.?\b", "saint", v)
    v = re.sub(r"\b(ft)\.?\b", "fort", v)
    v = re.sub(r"\b(mt)\.?\b", "mount", v)
    v = re.sub(r"\b(twp|township)\b", "", v)
    return re.sub(r"[^a-z0-9]+", " ", v).strip()


def load_gazetteer(path):
    out = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            k = (normalize_city(r["city"]), r["state"].strip().upper())
            v = (float(r["lat"]), float(r["lng"]), int(float(r.get("population") or 0)), r["city"])
            if k not in out or v[2] > out[k][2]:
                out[k] = v
    return out


def load_manual(path):
    out = {}
    if not path or not Path(path).exists():
        return out
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            out[(normalize_city(r["city"]), r["state"].strip().upper())] = (
                float(r["lat"]),
                float(r["lng"]),
                r.get("note", "manual"),
            )
    return out


def resolve_city(city, state, gazetteer, manual):
    k = (normalize_city(city), state.upper())
    if k in manual:
        return manual[k][0], manual[k][1], "manual"
    if k in gazetteer:
        return gazetteer[k][0], gazetteer[k][1], "city"
    choices = [n for n, s in gazetteer if s == state.upper()]
    m = difflib.get_close_matches(k[0], choices, n=1, cutoff=0.9)
    if m:
        return gazetteer[(m[0], state.upper())][0], gazetteer[(m[0], state.upper())][1], "fuzzy"
    return None, None, "unresolved"


class Command(BaseCommand):
    def add_arguments(self, p):
        p.add_argument("csv_path", type=Path, nargs="?", default=Path("data/fuel_prices.csv"))
        p.add_argument("--gazetteer", type=Path)
        p.add_argument("--manual-geocodes", type=Path, default=Path("data/manual_geocodes.csv"))
        p.add_argument("--from-geocoded", type=Path)
        p.add_argument("--price-rule", choices=("median", "min", "max", "mean"), default="median")

    def handle(self, *args, **o):
        path = o["csv_path"]
        geo = o.get("gazetteer")
        from_geo = o.get("from_geocoded")
        if from_geo:
            if not from_geo.exists():
                raise CommandError(f"Geocoded CSV not found: {from_geo}")
            objects = []
            rows = list(csv.DictReader(from_geo.open(newline="", encoding="utf-8-sig")))
            for r in rows:
                objects.append(
                    FuelStation(
                        opis_id=int(r["opis_id"]),
                        name=r["name"],
                        address=r["address"],
                        city=r["city"],
                        state=r["state"],
                        latitude=float(r["lat"]) if r["lat"] else None,
                        longitude=float(r["lng"]) if r["lng"] else None,
                        price_usd_per_gallon=Decimal(r["price"]),
                        price_min=Decimal(r["price_min"]),
                        price_max=Decimal(r["price_max"]),
                        price_rows_merged=int(r["rows_merged"]),
                        geocode_quality=r["geocode_quality"],
                    )
                )
            rows_read = len(rows)
            us_rows = rows
            groups = {}
            unresolved = [f"{x.city}, {x.state}" for x in objects if x.latitude is None]
        else:
            if not path.exists():
                raise CommandError(f"CSV not found: {path}")
            rows = list(csv.DictReader(path.open(newline="", encoding="utf-8-sig")))
            us_rows = [r for r in rows if r["State"].strip().upper() in US_STATES]
            groups = {}
            for r in us_rows:
                groups.setdefault(int(r["OPIS Truckstop ID"]), []).append(r)
            gazetteer = load_gazetteer(geo) if geo and geo.exists() else {}
            manual = load_manual(o.get("manual_geocodes"))
            objects = []
            unresolved = []
            for ident, g in groups.items():
                vals = [float(r["Retail Price"]) for r in g]
                first = g[0]
                rule = o["price_rule"]
                aggregate = (
                    min(vals)
                    if rule == "min"
                    else max(vals)
                    if rule == "max"
                    else statistics.mean(vals)
                    if rule == "mean"
                    else statistics.median(vals)
                )
                city = first["City"].strip()
                state = first["State"].strip().upper()
                lat, lng, quality = resolve_city(city, state, gazetteer, manual)
                if quality == "unresolved":
                    unresolved.append(f"{city}, {state}")
                objects.append(
                    FuelStation(
                        opis_id=ident,
                        name=max((r["Truckstop Name"].strip() for r in g), key=len),
                        address=first["Address"].strip(),
                        city=city,
                        state=state,
                        latitude=lat,
                        longitude=lng,
                        price_usd_per_gallon=Decimal(f"{aggregate:.4f}"),
                        price_min=Decimal(f"{min(vals):.4f}"),
                        price_max=Decimal(f"{max(vals):.4f}"),
                        price_rows_merged=len(vals),
                        geocode_quality=quality,
                    )
                )
            rows_read = len(rows)
        with transaction.atomic():
            FuelStation.objects.bulk_create(
                objects,
                update_conflicts=True,
                unique_fields=["opis_id"],
                update_fields=[
                    "name",
                    "address",
                    "city",
                    "state",
                    "latitude",
                    "longitude",
                    "price_usd_per_gallon",
                    "price_rows_merged",
                    "price_min",
                    "price_max",
                    "geocode_quality",
                ],
            )
            digest = hashlib.sha256(
                str(
                    [
                        (x.opis_id, str(x.price_usd_per_gallon), x.latitude, x.longitude)
                        for x in objects
                    ]
                ).encode()
            ).hexdigest()[:16]
            ImportRun.objects.update_or_create(
                data_version=digest,
                defaults={"source_name": str(from_geo or path), "price_rule": o["price_rule"]},
            )
        self.stdout.write(f"Rows read:                {rows_read}")
        self.stdout.write(f"Dropped (non-US):          {rows_read - len(us_rows)}")
        self.stdout.write(f"US rows:                  {len(us_rows)}")
        self.stdout.write(f"Unique stations:          {len(objects)}")
        self.stdout.write(
            f"IDs with multiple prices: {sum(len(g) > 1 for g in groups.values()) if not from_geo else 0}  (rule={o['price_rule']})"
        )
        self.stdout.write(
            f"Geocoded (city match):    {sum(x.geocode_quality == 'city' for x in objects)}"
        )
        self.stdout.write(f"Unresolved:                {len(unresolved)}   (listed below)")
        if unresolved:
            self.stdout.write("Unresolved cities: " + ", ".join(sorted(set(unresolved))))
