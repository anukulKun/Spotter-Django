"""Shared provider protocols and routing exceptions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GeoPoint:
    """A latitude/longitude point."""

    lat: float
    lng: float


class RoutingProviderError(Exception):
    """Base error for routing-provider failures."""


class NoRouteError(RoutingProviderError):
    """The provider could not find a route."""


class RoutingTimeout(RoutingProviderError):
    """The provider request timed out."""


class RoutingProvider(Protocol):
    """Protocol implemented by route providers."""

    def route(self, start: GeoPoint, finish: GeoPoint) -> dict:
        """Return normalized route data."""
        ...
