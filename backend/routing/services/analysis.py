"""Turns a trip request into scored routes, checkpoints and the corridor heatmap data."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, replace

from django.conf import settings

from ..domain import departure as departure_planner
from ..domain import ranking, sampling
from ..domain.forecast import HOUR, sample
from ..domain.geo import LatLon, simplify
from ..domain.path import Path
from ..domain.risk import RAIN_IN_HR, SNOW_IN_HR, WIND_MPH, Assessment, Risk, assess
from ..limits import MAX_DEPARTURE_AHEAD
from . import open_meteo, osrm

HEATMAP_HOURS = 48
PLAN_HOURS = 48          # how far ahead to score alternative departure times
# 25 mi matches the default checkpoint spacing, so the heatmap normally needs no extra forecast lookups.
HEATMAP_MIN_SPACING_MI = 25
HEATMAP_MAX_POINTS_PER_ROUTE = 50
GEOMETRY_TOLERANCE_DEG = 0.0015  # ~170 m: invisible at map scale, ~10x fewer points to send


@dataclass(frozen=True)
class TripRequest:
    origin: LatLon
    destination: LatLon
    departure_epoch: int
    load_lb: int
    interval_mi: int


@dataclass
class _Checkpoint:
    index: int
    mile: float
    covered_miles: float
    lat: float
    lon: float
    eta_epoch: int
    timezone: str
    utc_offset_s: int
    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float
    outside_forecast: bool
    assessment: Assessment


def analyze(req: TripRequest) -> dict:
    raw_routes = osrm.fetch_routes(req.origin, req.destination)
    paths = {f"r{i}": r.path for i, r in enumerate(raw_routes, start=1)}
    warnings: list[str] = []

    if len(paths) < 3:
        warnings.append(f"Only {len(paths)} distinct route(s) could be found for this trip.")

    interval = _common_interval(paths, req.interval_mi)
    if interval != req.interval_mi:
        warnings.append(
            f"Checkpoints are spaced every {interval:g} mi instead of {req.interval_mi} mi "
            "because this trip is very long."
        )

    # Work out where everything is first, so all weather is fetched in one batched pass.
    slots = {rid: sampling.plan_checkpoints(p.total_miles, interval) for rid, p in paths.items()}
    positions = {
        rid: [p.at_mile(s.mile) for s in slots[rid]] for rid, p in paths.items()
    }
    heat_spacing = _heatmap_spacing(paths)
    heat_points = _heatmap_points(paths, heat_spacing)

    wanted = [open_meteo.snap((pt.lat, pt.lon)) for pts in positions.values() for pt in pts]
    wanted += [open_meteo.snap(p) for p in heat_points]
    series = open_meteo.get_series(wanted)

    checkpoints = {
        rid: _build_checkpoints(slots[rid], positions[rid], series, req) for rid in paths
    }
    if any(cp.outside_forecast for cps in checkpoints.values() for cp in cps):
        warnings.append(
            "Part of this trip falls beyond the available forecast; the last available hour is used there."
        )

    stats = {
        rid: ranking.RouteStats(
            route_id=rid,
            duration_s=paths[rid].total_seconds,
            miles_by_risk=_miles_by_risk(checkpoints[rid]),
        )
        for rid in paths
    }
    ordered = ranking.rank(list(stats.values()))
    names = {rid: f"Route {rid[1:]}" for rid in paths}
    reasons = ranking.explain(ordered[0], ordered[1:], names)

    fastest_id = min(paths, key=lambda rid: paths[rid].total_seconds)
    fastest_s = paths[fastest_id].total_seconds

    routes_out = []
    for position, st in enumerate(ordered, start=1):
        rid = st.route_id
        raw = raw_routes[int(rid[1:]) - 1]
        routes_out.append(
            {
                "id": rid,
                "name": names[rid],
                "via": raw.via,
                "rank": position,
                "recommended": position == 1,
                "fastest": rid == fastest_id,
                "distance_mi": round(paths[rid].total_miles, 1),
                "duration_s": round(paths[rid].total_seconds),
                "extra_s_vs_fastest": round(paths[rid].total_seconds - fastest_s),
                "departure_epoch": req.departure_epoch,
                "arrival_epoch": req.departure_epoch + round(paths[rid].total_seconds),
                "summary": {
                    "max_risk": int(st.max_risk),
                    "avg_risk": round(st.avg_risk, 2),
                    "miles_by_risk": {
                        lvl.name.lower(): round(st.miles_by_risk.get(lvl, 0.0), 1) for lvl in Risk
                    },
                },
                "reasons": reasons if position == 1 else [],
                "geometry": [
                    [round(lat, 5), round(lon, 5)]
                    for lat, lon in simplify(paths[rid].points, GEOMETRY_TOLERANCE_DEG)
                ],
                "checkpoints": [_checkpoint_json(cp) for cp in checkpoints[rid]],
            }
        )

    return {
        "recommended_route_id": ordered[0].route_id,
        "interval_mi": interval,
        "warnings": warnings,
        "routes": routes_out,
        "departure_plan": _departure_plan(req, paths, slots, positions, series),
        "heatmap": _build_heatmap(heat_points, heat_spacing, series, req),
    }


def _common_interval(paths: dict[str, Path], requested: int) -> float:
    longest = max(p.total_miles for p in paths.values())
    return sampling.effective_interval(
        longest, requested, settings.ALLOWED_INTERVALS_MI, settings.MAX_CHECKPOINTS_PER_ROUTE
    )


def _build_checkpoints(slots, positions, series, req: TripRequest) -> list[_Checkpoint]:
    out = []
    for i, (slot, pos) in enumerate(zip(slots, positions)):
        s = series[open_meteo.snap((pos.lat, pos.lon))]
        eta = req.departure_epoch + pos.seconds
        wx = sample(s, eta)
        a = assess(wx.wind_mph, wx.rain_in_hr, wx.snow_in_hr, req.load_lb)
        out.append(
            _Checkpoint(
                index=i,
                mile=slot.mile,
                covered_miles=slot.covered_miles,
                lat=pos.lat,
                lon=pos.lon,
                eta_epoch=round(eta),
                timezone=s.timezone,
                utc_offset_s=s.utc_offset_s,
                wind_mph=round(wx.wind_mph, 1),
                rain_in_hr=round(wx.rain_in_hr, 2),
                snow_in_hr=round(wx.snow_in_hr, 2),
                outside_forecast=wx.outside_forecast,
                assessment=a,
            )
        )
    return out


def _miles_by_risk(checkpoints: list[_Checkpoint]) -> dict[Risk, float]:
    miles = {lvl: 0.0 for lvl in Risk}
    for cp in checkpoints:
        miles[cp.assessment.level] += cp.covered_miles
    return miles


def _checkpoint_json(cp: _Checkpoint) -> dict:
    a = cp.assessment
    return {
        "index": cp.index,
        "mile": round(cp.mile, 1),
        "covered_miles": round(cp.covered_miles, 1),
        "lat": round(cp.lat, 5),
        "lon": round(cp.lon, 5),
        "eta_epoch": cp.eta_epoch,
        "timezone": cp.timezone,
        "wind_mph": cp.wind_mph,
        "rain_in_hr": cp.rain_in_hr,
        "snow_in_hr": cp.snow_in_hr,
        "risk": int(a.level),
        "wind_risk": int(a.wind_level),
        "rain_risk": int(a.rain_level),
        "snow_risk": int(a.snow_level),
        "reason": a.reason,
    }


# ---- departure planning ----------------------------------------------------------------------


def _departure_plan(req: TripRequest, paths, slots, positions, series) -> dict:
    """Re-score every route for each start time in the next 48 h and say when to leave.

    No extra API calls: the forecasts already fetched cover these times, so this is just the same
    checkpoint scoring with the departure shifted. Start times that would need forecast we don't
    have (or that the API would refuse as too far ahead) are left out rather than guessed.
    """
    latest_allowed = time.time() + MAX_DEPARTURE_AHEAD.total_seconds()
    options: list[departure_planner.DepartureOption] = []
    for h in range(PLAN_HOURS + 1):
        shifted = replace(req, departure_epoch=req.departure_epoch + h * HOUR)
        if shifted.departure_epoch > latest_allowed:
            break
        stats, covered = [], True
        for rid, path in paths.items():
            cps = _build_checkpoints(slots[rid], positions[rid], series, shifted)
            if any(cp.outside_forecast for cp in cps):
                covered = False
                break
            stats.append(ranking.RouteStats(rid, path.total_seconds, _miles_by_risk(cps)))
        if not covered:
            break
        options.append(departure_planner.DepartureOption(h, ranking.rank(stats)[0]))

    chosen = departure_planner.best_offset(options)
    return {
        "recommended_offset_h": chosen,
        "message": departure_planner.explain(options, chosen),
        "options": [
            {
                "offset_h": o.offset_h,
                "epoch": req.departure_epoch + o.offset_h * HOUR,
                "best_route_id": o.best.route_id,
                "max_risk": int(o.best.max_risk),
                "avg_risk": round(o.best.avg_risk, 2),
                "no_travel_mi": round(o.best.miles_by_risk.get(Risk.NO_TRAVEL, 0.0)),
                "severe_mi": round(o.best.miles_by_risk.get(Risk.SEVERE, 0.0)),
                "high_mi": round(o.best.miles_by_risk.get(Risk.HIGH, 0.0)),
            }
            for o in options
        ],
    }


# ---- heatmap -------------------------------------------------------------------------------


def _heatmap_spacing(paths: dict[str, Path]) -> float:
    longest = max(p.total_miles for p in paths.values())
    return max(HEATMAP_MIN_SPACING_MI, math.ceil(longest / HEATMAP_MAX_POINTS_PER_ROUTE))


def _heatmap_points(paths: dict[str, Path], spacing: float) -> list[LatLon]:
    """Points along every route, one per weather-grid cell, so shared road isn't sampled twice."""
    by_cell: dict[LatLon, LatLon] = {}
    for path in paths.values():
        for mile in sampling.checkpoint_miles(path.total_miles, spacing):
            pt = path.at_mile(mile)
            by_cell.setdefault(open_meteo.snap((pt.lat, pt.lon)), (pt.lat, pt.lon))
    return list(by_cell.values())


def _build_heatmap(points: list[LatLon], spacing: float, series, req: TripRequest) -> dict:
    """Hour-by-hour conditions (departure to +48 h) for each corridor point.

    Risk is computed here, with the same rules and load as the route scoring, so the heatmap
    and the route cards can never disagree.
    """
    start = req.departure_epoch // HOUR * HOUR
    out = []
    for lat, lon in points:
        s = series[open_meteo.snap((lat, lon))]
        wind, rain, snow, risk = [], [], [], []
        for h in range(HEATMAP_HOURS + 1):
            wx = sample(s, start + h * HOUR)
            a = assess(wx.wind_mph, wx.rain_in_hr, wx.snow_in_hr, req.load_lb)
            wind.append(round(wx.wind_mph, 1))
            rain.append(round(wx.rain_in_hr, 2))
            snow.append(round(wx.snow_in_hr, 2))
            risk.append(int(a.level))
        out.append(
            {"lat": round(lat, 4), "lon": round(lon, 4), "wind": wind, "rain": rain, "snow": snow, "risk": risk}
        )
    return {
        "start_epoch": start,
        "hours": HEATMAP_HOURS,
        "spacing_mi": spacing,
        "scales": {"wind": WIND_MPH.bounds, "rain": RAIN_IN_HR.bounds, "snow": SNOW_IN_HR.bounds},
        "points": out,
    }
