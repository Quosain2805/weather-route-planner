"""Small spherical-geometry helpers. All coordinates are (lat, lon) in degrees."""
from __future__ import annotations

import math

EARTH_RADIUS_MI = 3958.7613

LatLon = tuple[float, float]


def haversine_mi(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MI * math.asin(min(1.0, math.sqrt(h)))


def bearing_deg(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlon = lon2 - lon1
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def destination_point(origin: LatLon, bearing: float, miles: float) -> LatLon:
    """Point reached by travelling `miles` from `origin` along an initial `bearing`."""
    lat1, lon1 = map(math.radians, origin)
    brg = math.radians(bearing)
    ang = miles / EARTH_RADIUS_MI
    lat2 = math.asin(
        math.sin(lat1) * math.cos(ang) + math.cos(lat1) * math.sin(ang) * math.cos(brg)
    )
    lon2 = lon1 + math.atan2(
        math.sin(brg) * math.sin(ang) * math.cos(lat1),
        math.cos(ang) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180


def simplify(points: list[LatLon], tolerance_deg: float) -> list[LatLon]:
    """Iterative Ramer-Douglas-Peucker. Used only to shrink geometry sent to the browser."""
    n = len(points)
    if n < 3:
        return list(points)

    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        lo, hi = stack.pop()
        (ay, ax), (by, bx) = points[lo], points[hi]
        dx, dy = bx - ax, by - ay
        seg_len_sq = dx * dx + dy * dy
        max_d, idx = 0.0, -1
        for i in range(lo + 1, hi):
            py, px = points[i]
            if seg_len_sq == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len_sq))
                d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
            if d > max_d:
                max_d, idx = d, i
        if idx != -1 and max_d > tolerance_deg:
            keep[idx] = True
            stack.append((lo, idx))
            stack.append((idx, hi))
    return [p for p, k in zip(points, keep) if k]
