"""Weather-risk classification: the thresholds and load rules from the assessment brief.

Boundary convention (the brief's table has overlapping edges such as "0.10-0.25" next to
"0.25-0.50", so one has to be chosen and applied everywhere):

* A value sits in the *higher* band when it equals a lower bound: wind 35 mph is High,
  rain 0.25 in/hr is High, snow 1.0 in/hr is High.
* "No Travel" is `>= 55` for wind but strictly `> 1.00` (rain) and `> 3.0` (snow), exactly as
  the table is worded. So 1.00 in/hr of rain is still Severe.
* Values are rounded to display precision (wind 0.1 mph, precipitation 0.01 in/hr) *before*
  classifying, so what the driver reads on screen is always what was classified.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Risk(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return _LABELS[self]


_LABELS = {
    Risk.LOW: "Low",
    Risk.MODERATE: "Moderate",
    Risk.HIGH: "High",
    Risk.SEVERE: "Severe",
    Risk.NO_TRAVEL: "No Travel",
}


@dataclass(frozen=True)
class Scale:
    """Lower bounds of each band. Anything below `moderate` is Low."""

    moderate: float
    high: float
    severe: float
    no_travel: float
    no_travel_inclusive: bool

    @property
    def bounds(self) -> list[float]:
        """Lower bounds of Moderate, High, Severe and No Travel (used to colour the heatmap)."""
        return [self.moderate, self.high, self.severe, self.no_travel]


WIND_MPH = Scale(moderate=25, high=35, severe=45, no_travel=55, no_travel_inclusive=True)
RAIN_IN_HR = Scale(moderate=0.10, high=0.25, severe=0.50, no_travel=1.00, no_travel_inclusive=False)
SNOW_IN_HR = Scale(moderate=0.5, high=1.0, severe=2.0, no_travel=3.0, no_travel_inclusive=False)

# Load rules (wind combined with cargo weight, in pounds).
WIND_NO_TRAVEL_ANY_LOAD_MPH = 55
WIND_SEVERE_BAND_MPH = 45
WIND_HIGH_BAND_MPH = 35
LOAD_NO_TRAVEL_IN_SEVERE_WIND_LB = 30_000
LOAD_SEVERE_IN_HIGH_WIND_LB = 40_000


def classify(value: float, scale: Scale) -> Risk:
    if value > scale.no_travel or (scale.no_travel_inclusive and value == scale.no_travel):
        return Risk.NO_TRAVEL
    if value >= scale.severe:
        return Risk.SEVERE
    if value >= scale.high:
        return Risk.HIGH
    if value >= scale.moderate:
        return Risk.MODERATE
    return Risk.LOW


@dataclass(frozen=True)
class Assessment:
    level: Risk
    wind_level: Risk
    rain_level: Risk
    snow_level: Risk
    load_rule: str | None  # set when a load rule raised the overall level
    reason: str


def assess(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lb: float) -> Assessment:
    """Overall risk at one place and time for a given load.

    Overall = worst of the three individual hazards, then the load rules can only raise it.
    """
    wind = round(wind_mph, 1)
    rain = round(rain_in_hr, 2)
    snow = round(snow_in_hr, 2)

    wind_level = classify(wind, WIND_MPH)
    rain_level = classify(rain, RAIN_IN_HR)
    snow_level = classify(snow, SNOW_IN_HR)
    level = max(wind_level, rain_level, snow_level)

    load_rule: str | None = None
    load_level = Risk.LOW
    if wind >= WIND_NO_TRAVEL_ANY_LOAD_MPH:
        load_level = Risk.NO_TRAVEL
        load_rule = f"Wind of {wind:g} mph is {WIND_NO_TRAVEL_ANY_LOAD_MPH} mph or more: No Travel for any load"
    elif wind >= WIND_SEVERE_BAND_MPH and load_lb > LOAD_NO_TRAVEL_IN_SEVERE_WIND_LB:
        load_level = Risk.NO_TRAVEL
        load_rule = (
            f"Wind of {wind:g} mph with a {load_lb:,.0f} lb load "
            f"(over {LOAD_NO_TRAVEL_IN_SEVERE_WIND_LB:,} lb): No Travel"
        )
    elif wind >= WIND_HIGH_BAND_MPH and load_lb > LOAD_SEVERE_IN_HIGH_WIND_LB:
        load_level = Risk.SEVERE
        load_rule = (
            f"Wind of {wind:g} mph with a {load_lb:,.0f} lb load "
            f"(over {LOAD_SEVERE_IN_HIGH_WIND_LB:,} lb): Severe"
        )

    applied = None
    if load_level > level:
        level = load_level
        applied = load_rule

    return Assessment(
        level=level,
        wind_level=wind_level,
        rain_level=rain_level,
        snow_level=snow_level,
        load_rule=applied,
        reason=_reason(level, wind, rain, snow, wind_level, rain_level, snow_level, applied),
    )


def _reason(
    level: Risk,
    wind: float,
    rain: float,
    snow: float,
    wind_level: Risk,
    rain_level: Risk,
    snow_level: Risk,
    load_rule: str | None,
) -> str:
    if load_rule:
        return load_rule
    if level == Risk.LOW:
        return "Conditions within normal limits"
    parts = []
    if wind_level == level:
        parts.append(f"wind {wind:g} mph")
    if rain_level == level:
        parts.append(f"rain {rain:.2f} in/hr")
    if snow_level == level:
        parts.append(f"snow {snow:.2f} in/hr")
    return f"{level.label}: " + ", ".join(parts)
