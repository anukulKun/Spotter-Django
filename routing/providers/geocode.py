"""Location resolution using the local gazetteer and bounded Nominatim fallback."""

from __future__ import annotations

import csv
import difflib
import re
from dataclasses import dataclass
from pathlib import Path

import requests
from django.conf import settings

from routing.models import GeocodeCache

from .base import GeoPoint

LOWER_48 = (24.0, 49.5, -125.0, -66.0)
STATE_NAMES = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "district of columbia": "DC",
}
LOWER_48_CODES = set(STATE_NAMES.values()) - {"AK", "HI", "DC"}


def state_code(value: str) -> str | None:
    """Return a two-letter state code for an abbreviation or full state name."""
    token = " ".join(value.casefold().replace(".", "").split())
    return value.strip().upper() if len(token) == 2 else STATE_NAMES.get(token)


def normalize_city(value: str) -> str:
    """Normalize common city spelling variants for gazetteer lookup."""
    value = value.casefold().strip()
    value = re.sub(r"\b(st)\.?\b", "saint", value)
    value = re.sub(r"\b(ft)\.?\b", "fort", value)
    value = re.sub(r"\b(mt)\.?\b", "mount", value)
    value = re.sub(r"\b(twp|township)\b", "", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def in_lower_48(lat: float, lng: float) -> bool:
    """Return whether coordinates fall within the supported lower-48 envelope."""
    return LOWER_48[0] <= lat <= LOWER_48[1] and LOWER_48[2] <= lng <= LOWER_48[3]


class LocationError(Exception):
    """Base error for location resolution failures."""

    code = "LOCATION_NOT_FOUND"


class LocationNotInUs(LocationError):
    """A location explicitly identified as outside the United States."""

    code = "LOCATION_NOT_IN_US"


class LocationNotSupported(LocationError):
    """A US location outside the supported lower-48 or unsupported input form."""

    code = "LOCATION_NOT_SUPPORTED"


@dataclass(frozen=True)
class ResolvedLocation:
    """A resolved coordinate and the source used to resolve it."""

    point: GeoPoint
    resolved: str
    source: str


class Gazetteer:
    """In-memory city gazetteer with manual overrides and fuzzy fallback."""

    def __init__(self, path: Path):
        self.entries: dict[tuple[str, str], tuple[float, float, int, str]] = {}
        self.manual: dict[tuple[str, str], tuple[float, float, str]] = {}
        manual_path = Path(path).parent / "manual_geocodes.csv"
        if manual_path.exists():
            with manual_path.open(newline="", encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    key = (normalize_city(row["city"]), row["state"].strip().upper())
                    self.manual[key] = (float(row["lat"]), float(row["lng"]), row["city"])
        with Path(path).open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                key = (normalize_city(row["city"]), row["state"].strip().upper())
                value = (
                    float(row["lat"]),
                    float(row["lng"]),
                    int(float(row.get("population") or 0)),
                    row["city"],
                )
                if key not in self.entries or value[2] > self.entries[key][2]:
                    self.entries[key] = value

    def find(self, text: str) -> tuple[float, float, str, str]:
        """Resolve a city/state string from manual, exact, or fuzzy gazetteer data."""
        pieces = [part.strip() for part in text.split(",")]
        state_token = pieces[-1] if len(pieces) >= 2 else None
        state = state_code(state_token) if state_token else None
        if state_token and state is None:
            raise LocationNotSupported(
                "This API supports US locations in the lower 48 states, entered as 'City, ST' or 'lat,lng'."
            )
        if state and state not in LOWER_48_CODES:
            if state in {"AK", "HI", "DC"}:
                raise LocationNotSupported(
                    "This API supports US locations in the lower 48 states, entered as 'City, ST' or 'lat,lng'."
                )
            raise LocationNotInUs("That location is outside the supported US dataset.")
        city = ",".join(pieces[:-1]) if state_token else text
        key = (normalize_city(city), state) if state else None
        if key in self.manual:
            lat, lng, name = self.manual[key]
            return lat, lng, f"{name}, {state}", "manual"
        if key in self.entries:
            lat, lng, _, name = self.entries[key]
            return lat, lng, f"{name}, {state}", "gazetteer"
        choices = [
            (entry_key, value)
            for entry_key, value in self.entries.items()
            if not state or entry_key[1] == state
        ]
        exact = [item for item in choices if item[0][0] == normalize_city(city)]
        if exact:
            best = max(exact, key=lambda item: item[1][2])
        else:
            names = [item[0][0] for item in choices]
            matches = difflib.get_close_matches(normalize_city(city), names, n=1, cutoff=0.9)
            if not matches:
                raise LocationError("Location was not found in the lower-48 gazetteer.")
            best = max(
                (item for item in choices if item[0][0] == matches[0]), key=lambda item: item[1][2]
            )
        (_, resolved_state), (lat, lng, _, display) = best
        return lat, lng, f"{display}, {resolved_state}", "gazetteer"


_gazetteer: Gazetteer | None = None


def get_gazetteer() -> Gazetteer:
    """Return the process-local gazetteer, preferring the full file when available."""
    global _gazetteer
    if _gazetteer is None:
        data_dir = Path(settings.BASE_DIR) / "data"
        path = data_dir / "us_cities.csv"
        if not path.exists():
            path = data_dir / "us_cities_min.csv"
        _gazetteer = Gazetteer(path)
    return _gazetteer


def resolve_location(text: str, external_calls: list[int]) -> ResolvedLocation:
    """Resolve coordinates, local city names, or one bounded Nominatim request."""
    value = text.strip()
    try:
        lat, lng = (float(part.strip()) for part in value.split(","))
        if not in_lower_48(lat, lng):
            raise LocationNotSupported(
                "This API supports US locations in the lower 48 states, entered as 'City, ST' or 'lat,lng'."
            )
        return ResolvedLocation(GeoPoint(lat, lng), value, "coordinates")
    except ValueError:
        pass
    try:
        lat, lng, resolved, source = get_gazetteer().find(value)
        return ResolvedLocation(GeoPoint(lat, lng), resolved, source)
    except LocationNotInUs:
        raise
    except LocationNotSupported:
        raise
    except (LocationError, FileNotFoundError):
        pass
    query = f"{value}, USA"
    key = query.casefold()
    cached = GeocodeCache.objects.filter(query_normalized=key).first()
    if cached:
        return ResolvedLocation(
            GeoPoint(cached.latitude, cached.longitude), cached.display_name, "nominatim-cache"
        )
    external_calls[0] += 1
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "us"},
            headers={
                "User-Agent": getattr(
                    settings, "NOMINATIM_USER_AGENT", "spotter-fuel-route-assessment"
                )
            },
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()[0]
        lat, lng = float(result["lat"]), float(result["lon"])
    except (requests.RequestException, IndexError, KeyError, ValueError) as exc:
        raise LocationError("Location was not found. Use 'City, ST' or 'lat,lng'.") from exc
    if not in_lower_48(lat, lng):
        raise LocationNotSupported(
            "This API supports US locations in the lower 48 states, entered as 'City, ST' or 'lat,lng'."
        )
    display = result.get("display_name", value)
    GeocodeCache.objects.update_or_create(
        query_normalized=key,
        defaults={"latitude": lat, "longitude": lng, "display_name": display},
    )
    return ResolvedLocation(GeoPoint(lat, lng), display, "nominatim")
