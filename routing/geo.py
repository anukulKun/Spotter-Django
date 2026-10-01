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
    if len(lat) <= 1:
        return lat.copy(), lon.copy()
    distances = np.asarray(haversine_miles(lat[:-1], lon[:-1], lat[1:], lon[1:]), float)
    counts = np.maximum(1, np.ceil(distances / step_miles).astype(int))
    total = int(counts.sum())
    ends = np.cumsum(counts)
    starts = np.concatenate(([0], ends[:-1]))
    positions = np.arange(total)
    segment = np.searchsorted(ends, positions, side="right")
    t = (positions - starts[segment] + 1) / counts[segment]
    out_lat = lat[:-1][segment] + t * (lat[1:][segment] - lat[:-1][segment])
    out_lon = lon[:-1][segment] + t * (lon[1:][segment] - lon[:-1][segment])
    return np.concatenate(([lat[0]], out_lat)), np.concatenate(([lon[0]], out_lon))


def cumulative_miles(lat, lon, total_miles=None):
    if len(lat) < 2:
        return np.zeros(len(lat), dtype=float)
    segments = haversine_miles(lat[:-1], lon[:-1], lat[1:], lon[1:])
    cumulative = np.concatenate([[0.0], np.cumsum(segments)])
    if total_miles is not None and cumulative[-1] > 0:
        cumulative *= total_miles / cumulative[-1]
    return cumulative
