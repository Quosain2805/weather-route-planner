"""Driving routes from an OSRM server (the public demo by default, swappable via settings).

We ask OSRM for alternatives first. On shorter trips it often finds fewer than three, so we
top the list up with "via" routes: re-route through a waypoint pushed sideways off the
fastest route's midpoint, and keep the result only if it is a genuinely different, reasonable
drive.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

from ..domain.geo import LatLon, bearing_deg, destination_point
from ..domain.path import Path, Step
from ..domain.similarity import overlap_fraction
from .errors import NoRouteError, UpstreamError
from .http import get_json

log = logging.getLogger(__name__)

SERVICE = "Routing service"
WANT = 3
MAX_OVERLAP = 0.85         # a candidate sharing more road than this with a kept route is a duplicate
MAX_DURATION_RATIO = 1.6   # ignore silly detours against the fastest route
MAX_SNAP_MI = 15           # OSRM may snap a point to the nearest road; beyond this it's the wrong place
M_PER_MILE = 1609.344


@dataclass(frozen=True)
class RawRoute:
    steps: list[Step]
    via: str  # the main roads used, e.g. "I 80 · I 90"
    path: Path


def fetch_routes(origin: LatLon, destination: LatLon) -> list[RawRoute]:
    """Up to three distinct routes, fastest first."""
    key = f"osrm:v2:{origin[0]:.4f},{origin[1]:.4f}:{destination[0]:.4f},{destination[1]:.4f}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    routes = _route([origin, destination], alternatives=True)
    kept = _dedupe(routes)

    if len(kept) < WANT:
        kept = _top_up(origin, destination, kept)

    kept.sort(key=lambda r: r.path.total_seconds)
    kept = kept[:WANT]
    cache.set(key, kept, settings.ROUTE_CACHE_TTL_S)
    return kept


def _route(coords: list[LatLon], alternatives: bool) -> list[RawRoute]:
    path = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in coords)
    params = {
        "alternatives": WANT if alternatives else "false",
        "steps": "true",
        "geometries": "geojson",
        "overview": "false",
    }
    data = get_json(SERVICE, f"{settings.OSRM_URL}/route/v1/driving/{path}", params, timeout=30)

    code = data.get("code")
    if code in ("NoRoute", "NoSegment"):
        raise NoRouteError("No drivable route between those two places")
    if code != "Ok":
        raise UpstreamError(SERVICE, data.get("message") or f"routing failed ({code})")

    _check_snapping(data.get("waypoints", []), coords)

    routes = []
    for item in data.get("routes", []):
        raw = _parse(item)
        if raw:
            routes.append(raw)
    return routes


def _check_snapping(waypoints: list[dict], requested: list[LatLon]) -> None:
    """Reject trips whose endpoints were matched to roads far from where the user pointed.

    OSRM will happily snap a point in the middle of an ocean (or a different continent's road
    network, which is disconnected from this one) to the nearest road it *can* route from. That
    yields a confident but meaningless route, so only the first and last points are checked.
    """
    for index, label in ((0, "starting point"), (len(requested) - 1, "destination")):
        if index >= len(waypoints):
            continue
        snapped_m = waypoints[index].get("distance")
        if snapped_m is not None and snapped_m / M_PER_MILE > MAX_SNAP_MI:
            raise NoRouteError(
                f"No drivable route between those two places: the {label} couldn't be matched "
                "to a road connected to the other."
            )


def _parse(item: dict) -> RawRoute | None:
    steps: list[Step] = []
    road_miles: dict[str, float] = defaultdict(float)
    for leg in item.get("legs", []):
        for step in leg.get("steps", []):
            coords = [(lat, lon) for lon, lat in step["geometry"]["coordinates"]]
            road = (step.get("ref") or step.get("name") or "").replace(";", " /")
            steps.append(Step(coords=coords, duration_s=float(step.get("duration", 0)), road=road))
            if road:
                road_miles[road] += step.get("distance", 0) / M_PER_MILE
    try:
        path = Path.from_steps(steps)
    except ValueError:
        return None
    return RawRoute(steps=steps, via=_via_label(road_miles), path=path)


def _via_label(road_miles: dict[str, float]) -> str:
    """The two roads carrying most of the distance, skipping near-duplicates ("I 80" / "I 80 Express")."""
    chosen: list[str] = []
    for road in sorted(road_miles, key=road_miles.get, reverse=True):
        if any(road in c or c in road for c in chosen):
            continue
        chosen.append(road)
        if len(chosen) == 2:
            break
    return " · ".join(chosen)


def _dedupe(candidates: list[RawRoute], kept: list[RawRoute] | None = None) -> list[RawRoute]:
    kept = list(kept or [])
    for cand in candidates:
        if all(overlap_fraction(cand.path, k.path) <= MAX_OVERLAP for k in kept):
            kept.append(cand)
        if len(kept) >= WANT:
            break
    return kept


def _top_up(origin: LatLon, destination: LatLon, kept: list[RawRoute]) -> list[RawRoute]:
    primary = min(kept, key=lambda r: r.path.total_seconds).path
    total = primary.total_miles
    offset_mi = min(150.0, max(12.0, total * 0.15))

    # Try the midpoint first, then points either side of it; each ring is fetched in parallel.
    for fractions in ((0.5,), (0.35, 0.65)):
        vias = []
        for f in fractions:
            here = primary.at_mile(total * f)
            before = primary.at_mile(max(0.0, total * f - 5))
            after = primary.at_mile(min(total, total * f + 5))
            heading = bearing_deg((before.lat, before.lon), (after.lat, after.lon))
            for side in (90, -90):
                vias.append(destination_point((here.lat, here.lon), heading + side, offset_mi))

        def attempt(via: LatLon) -> RawRoute | None:
            try:
                found = _route([origin, via, destination], alternatives=False)
            except (UpstreamError, NoRouteError):
                return None
            return found[0] if found else None

        with ThreadPoolExecutor(max_workers=len(vias)) as pool:
            results = [r for r in pool.map(attempt, vias) if r]

        fastest = primary.total_seconds
        sensible = [r for r in results if r.path.total_seconds <= fastest * MAX_DURATION_RATIO]
        sensible.sort(key=lambda r: r.path.total_seconds)
        kept = _dedupe(sensible, kept)
        if len(kept) >= WANT:
            break
    return kept
