"""Cached in-memory fuel-station index."""

from __future__ import annotations

import threading

from .models import FuelStation

_lock = threading.Lock()
_data: list[dict] | None = None


def clear() -> None:
    """Clear the process-local station cache."""
    global _data
    with _lock:
        _data = None


def load() -> list[dict]:
    """Load all geocoded stations once from the database."""
    global _data
    if _data is None:
        with _lock:
            if _data is None:
                _data = list(
                    FuelStation.objects.filter(
                        latitude__isnull=False, longitude__isnull=False
                    ).values(
                        "opis_id",
                        "name",
                        "address",
                        "city",
                        "state",
                        "latitude",
                        "longitude",
                        "price_usd_per_gallon",
                    )
                )
    return _data


def stations() -> list[dict]:
    """Return the cached station rows."""
    return load()
