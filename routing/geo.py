"""Small, dependency-light geographic helpers."""
from __future__ import annotations

import math

import numpy as np

EARTH_R_MI = 3958.7613


def haversine_miles(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_R_MI * np.arcsin(np.sqrt(a))


def to_local_xy(lat, lon, lat0):
    x = np.radians(lon) * EARTH_R_MI * math.cos(math.radians(lat0))
    y = np.radians(lat) * EARTH_R_MI
    return np.column_stack([x, y])


def densify(lat, lon, step_miles=1.0):
    lat, lon = np.asarray(lat, float), np.asarray(lon, float)
    if len(lat) == 0:
        return lat, lon
    out_lat, out_lon = [lat[0]], [lon[0]]
    for i in range(1, len(lat)):
        distance = float(haversine_miles(lat[i - 1], lon[i - 1], lat[i], lon[i]))
        n = max(1, int(math.ceil(distance / step_miles)))
        for k in range(1, n + 1):
            t = k / n
            out_lat.append(lat[i - 1] + t * (lat[i] - lat[i - 1]))
            out_lon.append(lon[i - 1] + t * (lon[i] - lon[i - 1]))
    return np.array(out_lat), np.array(out_lon)


def cumulative_miles(lat, lon, total_miles=None):
    if len(lat) < 2:
        return np.zeros(len(lat), dtype=float)
    segments = haversine_miles(lat[:-1], lon[:-1], lat[1:], lon[1:])
    cumulative = np.concatenate([[0.0], np.cumsum(segments)])
    if total_miles is not None and cumulative[-1] > 0:
        cumulative *= total_miles / cumulative[-1]
    return cumulative
