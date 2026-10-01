import numpy as np
import pytest

from routing.geo import cumulative_miles, densify, haversine_miles


def test_lon_lat_order_regression():
    # Dallas to Chicago is roughly 800 crow-fly miles, not a tiny distance.
    distance = float(haversine_miles(32.7767, -96.7970, 41.8781, -87.6298))
    assert 700 < distance < 900


def test_densify_spacing_is_bounded():
    lat, lon = densify([32.77, 41.87], [-96.79, -87.62], step_miles=100)
    assert np.max(haversine_miles(lat[:-1], lon[:-1], lat[1:], lon[1:])) <= 100.0001


def test_cumulative_distance_scales_to_provider_distance():
    lat, lon = densify([32.77, 41.87], [-96.79, -87.62], step_miles=100)
    cumulative = cumulative_miles(lat, lon, total_miles=925.4)
    assert cumulative[0] == 0
    assert cumulative[-1] == pytest.approx(925.4)
