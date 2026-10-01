from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

from .geo import to_local_xy


@dataclass(frozen=True)
class CorridorHit:
    station_id: int
    mile: float
    price: float
    offset_miles: float


def match_corridor(
    route_lat, route_lon, cum_miles, st_lat, st_lon, st_ids, st_prices, corridor_miles=5.0
):
    lat0 = float(np.mean(route_lat))
    route_xy = to_local_xy(route_lat, route_lon, lat0)
    station_xy = to_local_xy(st_lat, st_lon, lat0)
    distances, indexes = cKDTree(route_xy).query(
        station_xy, k=1, distance_upper_bound=corridor_miles
    )
    hits = [
        CorridorHit(
            int(st_ids[j]), float(cum_miles[indexes[j]]), float(st_prices[j]), float(distances[j])
        )
        for j in np.where(np.isfinite(distances))[0]
    ]
    return sorted(hits, key=lambda hit: hit.mile)
