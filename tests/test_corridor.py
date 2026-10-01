import numpy as np

from routing.corridor import CorridorHit, match_corridor
from routing.geo import cumulative_miles, densify


def test_corridor_matches_nearby_stations_and_sorts_by_mile():
    route_lat, route_lon = densify([32.77, 33.77], [-96.79, -96.79], step_miles=1)
    cumulative = cumulative_miles(route_lat, route_lon)
    hits = match_corridor(
        route_lat, route_lon, cumulative,
        np.array([33.0, 33.2, 33.0]), np.array([-96.79, -96.79, -95.9]),
        np.array([1, 2, 3]), np.array([3.0, 3.1, 2.0]), corridor_miles=5,
    )
    assert all(isinstance(hit, CorridorHit) for hit in hits)
    assert [hit.station_id for hit in hits] == [1, 2]
    assert all(hit.offset_miles <= 5 for hit in hits)
    assert [hit.mile for hit in hits] == sorted(hit.mile for hit in hits)
