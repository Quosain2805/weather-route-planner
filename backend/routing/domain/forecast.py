"""Hourly point forecasts and sampling them at an arbitrary moment."""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

HOUR = 3600


@dataclass(frozen=True)
class HourlySeries:
    """Forecast for one location. Times are unix seconds (UTC), strictly increasing."""

    times: list[int]
    wind_mph: list[float]
    rain_in_hr: list[float]  # rain + showers
    snow_in_hr: list[float]
    timezone: str
    utc_offset_s: int


@dataclass(frozen=True)
class WeatherSample:
    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float
    outside_forecast: bool  # requested time was outside the data we hold (value is clamped)


def sample(series: HourlySeries, epoch: float) -> WeatherSample:
    """Linearly interpolate between the two surrounding hourly values.

    Outside the forecast window the nearest hour is used and flagged, rather than guessing.
    """
    times = series.times
    outside = epoch < times[0] or epoch > times[-1]
    if outside or len(times) == 1:
        i = 0 if epoch < times[0] else len(times) - 1
        return WeatherSample(series.wind_mph[i], series.rain_in_hr[i], series.snow_in_hr[i], outside)

    hi = bisect_right(times, epoch)
    if hi >= len(times):
        hi = len(times) - 1
    lo = hi - 1
    span = times[hi] - times[lo]
    f = (epoch - times[lo]) / span if span else 0.0

    def lerp(values: list[float]) -> float:
        return values[lo] + (values[hi] - values[lo]) * f

    return WeatherSample(lerp(series.wind_mph), lerp(series.rain_in_hr), lerp(series.snow_in_hr), False)
