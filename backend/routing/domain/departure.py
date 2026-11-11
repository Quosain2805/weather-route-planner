"""Choosing *when* to leave: pick the best start time among those that were scored.

Each option is the best route available if the truck departs `offset_h` hours after the requested
time. A later start is only recommended when it makes the weather meaningfully better, and the
earliest of equally good starts always wins, so we never suggest waiting for no reason.
"""
from __future__ import annotations

from dataclasses import dataclass

from .ranking import RouteStats
from .risk import Risk

MAX_DELAY_H = 24      # how far into the future we are willing to tell a driver to wait
AVG_RISK_STEP = 0.1   # average risk is compared at this resolution (tie-break only)

# Waiting costs a driver real time, so only advise it for a meaningful improvement:
# any drop in No Travel miles, or 10+ fewer Severe miles, or 25+ fewer High miles.
MIN_SEVERE_GAIN_MI = 10
MIN_HIGH_GAIN_MI = 25


@dataclass(frozen=True)
class DepartureOption:
    offset_h: int
    best: RouteStats  # the recommended route if leaving at this time


def quality_key(stats: RouteStats) -> tuple[int, int, int, float]:
    """Weather quality only (no travel time): No Travel, Severe, High miles, then average risk."""
    return (
        round(stats.miles_by_risk.get(Risk.NO_TRAVEL, 0.0)),
        round(stats.miles_by_risk.get(Risk.SEVERE, 0.0)),
        round(stats.miles_by_risk.get(Risk.HIGH, 0.0)),
        round(stats.avg_risk / AVG_RISK_STEP) * AVG_RISK_STEP,
    )


def _gain(here: tuple, there: tuple) -> str | None:
    """Which hazard improved enough to justify waiting, or None."""
    if there[0] < here[0]:
        return "No Travel miles"
    if here[1] - there[1] >= MIN_SEVERE_GAIN_MI:
        return "Severe miles"
    if here[2] - there[2] >= MIN_HIGH_GAIN_MI:
        return "High miles"
    return None


def best_offset(options: list[DepartureOption], max_delay_h: int = MAX_DELAY_H) -> int:
    """Hours to wait. 0 means the requested departure is already the best window."""
    if not options:
        return 0
    here = quality_key(options[0].best)
    worthwhile = [
        o for o in options if 0 < o.offset_h <= max_delay_h and _gain(here, quality_key(o.best))
    ]
    if not worthwhile:
        return 0
    # Best weather among the worthwhile starts, earliest among ties.
    return min(worthwhile, key=lambda o: (quality_key(o.best), o.offset_h)).offset_h


_INDEX = {"No Travel miles": 0, "Severe miles": 1, "High miles": 2}


def explain(options: list[DepartureOption], offset_h: int) -> str:
    if not options:
        return "No departure options could be scored."
    here = quality_key(options[0].best)
    if offset_h == 0:
        if here[:3] == (0, 0, 0):
            return "Your chosen departure looks good: no Severe or High weather on the way."
        return "No meaningfully better start time in the next 24 hours: your chosen departure is fine."

    chosen = next(o for o in options if o.offset_h == offset_h)
    there = quality_key(chosen.best)
    label = _gain(here, there)
    i = _INDEX[label]
    unit = "hour" if offset_h == 1 else "hours"
    return f"Leave {offset_h} {unit} later and {label} fall from {here[i]} to {there[i]}."
