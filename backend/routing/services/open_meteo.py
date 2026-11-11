"""Hourly wind / rain / snow forecasts from Open-Meteo (free, no API key).

Units are requested directly in the units the risk rules use (mph, inches). Hourly precipitation
in Open-Meteo is the total over the preceding hour, so inches-per-hour needs no conversion.
Rain risk uses `rain + showers`, since convective showers would otherwise be missed.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.core.cache import cache

from ..domain.forecast import HourlySeries
from ..domain.geo import LatLon
from .errors import UpstreamError
from .http import get_json

log = logging.getLogger(__name__)

HOURLY_VARS = "wind_speed_10m,rain,showers,snowfall"
CACHE_PREFIX = "wx:v1:"
BATCH_SIZE = 40


def snap(point: LatLon) -> LatLon:
    """Round to the weather grid (0.1 deg, ~7 mi). Nearby lookups, including those on different
    routes, then share one forecast request and one cache entry."""
    step = settings.WEATHER_GRID_DEG
    return (round(round(point[0] / step) * step, 4), round(round(point[1] / step) * step, 4))


def _key(p: LatLon) -> str:
    return f"{CACHE_PREFIX}{p[0]:.3f},{p[1]:.3f}"


def get_series(points: list[LatLon]) -> dict[LatLon, HourlySeries]:
    """Forecast for every (already snapped) point, fetching only what the cache is missing."""
    unique = list(dict.fromkeys(points))
    cached = cache.get_many([_key(p) for p in unique])
    result: dict[LatLon, HourlySeries] = {p: cached[_key(p)] for p in unique if _key(p) in cached}

    missing = [p for p in unique if p not in result]
    if missing:
        batches = [missing[i : i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]
        with ThreadPoolExecutor(max_workers=min(4, len(batches))) as pool:
            fetched = list(pool.map(_fetch_batch, batches))
        fresh: dict[LatLon, HourlySeries] = {}
        for batch, series_list in zip(batches, fetched):
            fresh.update(zip(batch, series_list))
        cache.set_many({_key(p): s for p, s in fresh.items()}, settings.WEATHER_CACHE_TTL_S)
        result.update(fresh)
    return result


def _fetch_batch(batch: list[LatLon]) -> list[HourlySeries]:
    params = {
        "latitude": ",".join(f"{lat:.4f}" for lat, _ in batch),
        "longitude": ",".join(f"{lon:.4f}" for _, lon in batch),
        "hourly": HOURLY_VARS,
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timeformat": "unixtime",
        "timezone": "auto",
        "past_days": 1,
        "forecast_days": settings.WEATHER_FORECAST_DAYS,
    }
    if settings.OPEN_METEO_API_KEY:
        params["apikey"] = settings.OPEN_METEO_API_KEY
    payload = get_json("Weather service", settings.OPEN_METEO_URL, params, timeout=25)
    if isinstance(payload, dict) and payload.get("error"):
        reason = str(payload.get("reason", "weather request rejected"))
        if "limit" in reason.lower():
            raise UpstreamError("Weather service", "Weather service rate limit reached; try again in a minute.", 503)
        raise UpstreamError("Weather service", reason)

    locations = payload if isinstance(payload, list) else [payload]
    if len(locations) != len(batch):
        raise UpstreamError("Weather service", "weather response did not match the request")
    return [_parse(loc) for loc in locations]


def _parse(loc: dict) -> HourlySeries:
    hourly = loc.get("hourly") or {}
    times = hourly.get("time")
    if not times:
        raise UpstreamError("Weather service", "weather response had no hourly data")

    def column(name: str) -> list[float]:
        return [v if v is not None else 0.0 for v in hourly.get(name, [])]

    wind = column("wind_speed_10m")
    rain = column("rain")
    showers = column("showers") or [0.0] * len(rain)
    snow = column("snowfall")
    if not (len(wind) == len(rain) == len(showers) == len(snow) == len(times)):
        raise UpstreamError("Weather service", "weather response had inconsistent series")

    return HourlySeries(
        times=list(times),
        wind_mph=wind,
        rain_in_hr=[round(r + s, 4) for r, s in zip(rain, showers)],
        snow_in_hr=snow,
        timezone=loc.get("timezone", "UTC"),
        utc_offset_s=int(loc.get("utc_offset_seconds", 0)),
    )
