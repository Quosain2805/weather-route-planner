"""A drivable path with cumulative distance and time, queryable by mile marker."""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from .geo import LatLon, haversine_mi


@dataclass(frozen=True)
class Step:
    """One routing-API manoeuvre: its geometry, how long it takes, and the road it is on."""

    coords: list[LatLon]
    duration_s: float
    road: str = ""


@dataclass(frozen=True)
class PathPoint:
    mile: float
    lat: float
    lon: float
    seconds: float  # time since departure


class Path:
    def __init__(self, points: list[LatLon], cum_miles: list[float], cum_seconds: list[float]):
        if not points or not (len(points) == len(cum_miles) == len(cum_seconds)):
            raise ValueError("Path needs matching, non-empty point/distance/time lists")
        self.points = points
        self.cum_miles = cum_miles
        self.cum_seconds = cum_seconds

    @property
    def total_miles(self) -> float:
        return self.cum_miles[-1]

    @property
    def total_seconds(self) -> float:
        return self.cum_seconds[-1]

    @classmethod
    def from_steps(cls, steps: list[Step]) -> "Path":
        """Build a path from routing steps.

        Each step's duration is spread over its own segments in proportion to length, so
        time-along-route reflects real speed changes (highway vs. city) rather than one
        average speed for the whole trip.
        """
        points: list[LatLon] = []
        miles: list[float] = []
        seconds: list[float] = []
        for step in steps:
            coords = step.coords
            if not coords:
                continue
            if not points:
                points.append(coords[0])
                miles.append(0.0)
                seconds.append(0.0)
            elif haversine_mi(points[-1], coords[0]) > 1e-6:
                # Steps normally share an endpoint; bridge a gap rather than teleport.
                coords = [points[-1], *coords]

            seg = [haversine_mi(a, b) for a, b in zip(coords, coords[1:])]
            step_len = sum(seg)
            if step_len == 0:
                seconds[-1] += step.duration_s  # time passes (e.g. a ferry wait) but no distance
                continue
            for end, length in zip(coords[1:], seg):
                points.append(end)
                miles.append(miles[-1] + length)
                seconds.append(seconds[-1] + step.duration_s * length / step_len)
        if len(points) < 2:
            raise ValueError("Route has no usable geometry")
        return cls(points, miles, seconds)

    def at_mile(self, mile: float) -> PathPoint:
        mile = max(0.0, min(mile, self.total_miles))
        i = bisect_right(self.cum_miles, mile)
        if i >= len(self.points):
            lat, lon = self.points[-1]
            return PathPoint(self.total_miles, lat, lon, self.total_seconds)
        if i == 0:
            lat, lon = self.points[0]
            return PathPoint(0.0, lat, lon, 0.0)
        span = self.cum_miles[i] - self.cum_miles[i - 1]
        f = (mile - self.cum_miles[i - 1]) / span if span > 0 else 0.0
        (lat0, lon0), (lat1, lon1) = self.points[i - 1], self.points[i]
        return PathPoint(
            mile,
            lat0 + (lat1 - lat0) * f,
            lon0 + (lon1 - lon0) * f,
            self.cum_seconds[i - 1] + (self.cum_seconds[i] - self.cum_seconds[i - 1]) * f,
        )
