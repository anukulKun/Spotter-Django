from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lng: float
class RoutingProviderError(Exception): pass
class NoRouteError(RoutingProviderError): pass
class RoutingTimeout(RoutingProviderError): pass
class RoutingProvider(Protocol):
    def route(self, start: GeoPoint, finish: GeoPoint) -> dict: ...
