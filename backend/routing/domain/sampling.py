"""Choosing weather checkpoints along a route and the stretch of road each one speaks for."""
from __future__ import annotations

import math
from dataclasses import dataclass

# Avoid a trailing checkpoint sitting right next to the destination.
MIN_TAIL_FRACTION = 0.25


@dataclass(frozen=True)
class CheckpointSlot:
    mile: float
    covers_from: float
    covers_to: float

    @property
    def covered_miles(self) -> float:
        return self.covers_to - self.covers_from


def checkpoint_miles(total_miles: float, interval: float) -> list[float]:
    """Mile markers: origin, every `interval` miles, and always the destination."""
    if total_miles <= 0:
        return [0.0]
    miles = [i * interval for i in range(int(total_miles // interval) + 1)]
    if total_miles - miles[-1] > 1e-9:
        if len(miles) > 1 and total_miles - miles[-1] < MIN_TAIL_FRACTION * interval:
            miles.pop()
        miles.append(total_miles)
    return miles


def plan_checkpoints(total_miles: float, interval: float) -> list[CheckpointSlot]:
    """Checkpoints plus coverage: each one represents the road halfway to its neighbours.

    Coverage tiles the route exactly, so per-risk mileage always sums to the route length.
    """
    miles = checkpoint_miles(total_miles, interval)
    slots = []
    for i, mile in enumerate(miles):
        start = 0.0 if i == 0 else (miles[i - 1] + mile) / 2
        end = total_miles if i == len(miles) - 1 else (mile + miles[i + 1]) / 2
        slots.append(CheckpointSlot(mile, start, end))
    return slots


def effective_interval(
    total_miles: float, requested: int, allowed: tuple[int, ...], max_points: int
) -> float:
    """Smallest allowed interval >= the request that keeps the checkpoint count under the cap.

    A very long route at 10-mile spacing would mean hundreds of weather lookups per route, so
    the interval is coarsened (and the UI told) rather than failing the request.
    """
    for candidate in sorted(a for a in allowed if a >= requested):
        if len(checkpoint_miles(total_miles, candidate)) <= max_points:
            return candidate
    return math.ceil(total_miles / max_points)
