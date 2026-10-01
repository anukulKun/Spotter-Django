"""OSRM routing provider adapter."""

from __future__ import annotations

import requests
from django.conf import settings

from .base import GeoPoint, NoRouteError, RoutingProviderError, RoutingTimeout

METERS_PER_MILE = 1609.344
_SESSION = requests.Session()
_PROVIDER = None


def meters_to_miles(meters: float) -> float:
    """Convert OSRM meters to statute miles."""
    return float(meters) / METERS_PER_MILE


class OsrmProvider:
    """Call OSRM and normalize its route response."""

    def __init__(self, session=None):
        self.session = session or _SESSION
        self.base_url = getattr(
            settings, "OSRM_BASE_URL", "https://router.project-osrm.org"
        ).rstrip("/")
        self.timeout = float(getattr(settings, "ROUTING_TIMEOUT_SECONDS", 10))
        self.user_agent = getattr(settings, "NOMINATIM_USER_AGENT", "spotter-fuel-route-assessment")

    def route(self, start: GeoPoint, finish: GeoPoint) -> dict:
        """Request a driving route from OSRM."""
        url = f"{self.base_url}/route/v1/driving/{start.lng},{start.lat};{finish.lng},{finish.lat}"
        params = {"overview": "full", "geometries": "geojson", "steps": "false"}
        headers = {"User-Agent": self.user_agent}
        try:
            response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
        except requests.Timeout as exc:
            raise RoutingTimeout("OSRM request timed out") from exc
        except requests.ConnectionError:
            try:
                response = self.session.get(
                    url, params=params, headers=headers, timeout=self.timeout
                )
            except requests.Timeout as exc:
                raise RoutingTimeout("OSRM request timed out") from exc
            except requests.RequestException as exc:
                raise RoutingProviderError(str(exc)) from exc
        except requests.RequestException as exc:
            raise RoutingProviderError(str(exc)) from exc
        if response.status_code >= 400:
            raise RoutingProviderError(f"OSRM HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise RoutingProviderError("OSRM returned invalid JSON") from exc
        if payload.get("code") != "Ok" or not payload.get("routes"):
            raise NoRouteError(payload.get("message", "No drivable route"))
        route = payload["routes"][0]
        return {
            "distance_miles": meters_to_miles(route["distance"]),
            "duration_hours": float(route.get("duration", 0)) / 3600,
            "geometry": route["geometry"],
            "provider": "osrm",
        }


def default_provider():
    """Return the process-local default OSRM provider."""
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = OsrmProvider(_SESSION)
    return _PROVIDER
