import pytest

from routing.domain.risk import RAIN_IN_HR, SNOW_IN_HR, WIND_MPH, Risk, assess, classify

L, M, H, S, N = Risk.LOW, Risk.MODERATE, Risk.HIGH, Risk.SEVERE, Risk.NO_TRAVEL


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, L), (24.9, L),
        (25, M), (34.9, M),
        (35, H), (44.9, H),
        (45, S), (54.9, S),
        (55, N), (80, N),
    ],
)
def test_wind_bands(value, expected):
    assert classify(value, WIND_MPH) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, L), (0.09, L),
        (0.10, M), (0.24, M),
        (0.25, H), (0.49, H),
        (0.50, S), (1.00, S),   # 1.00 is still Severe: No Travel is strictly "> 1.00"
        (1.01, N), (3, N),
    ],
)
def test_rain_bands(value, expected):
    assert classify(value, RAIN_IN_HR) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, L), (0.4, L),
        (0.5, M), (0.9, M),
        (1.0, H), (1.9, H),
        (2.0, S), (3.0, S),     # 3.0 is still Severe: No Travel is strictly "> 3.0"
        (3.1, N),
    ],
)
def test_snow_bands(value, expected):
    assert classify(value, SNOW_IN_HR) == expected


def test_overall_is_worst_hazard():
    a = assess(wind_mph=10, rain_in_hr=0.30, snow_in_hr=0.6, load_lb=10_000)
    assert (a.wind_level, a.rain_level, a.snow_level) == (L, H, M)
    assert a.level == H
    assert a.load_rule is None


def test_calm_and_dry_is_low():
    assert assess(5, 0, 0, 80_000).level == L


# ---- load rules -------------------------------------------------------------------------------

@pytest.mark.parametrize("load", [0, 10_000, 80_000])
def test_wind_55_is_no_travel_for_any_load(load):
    assert assess(55, 0, 0, load).level == N


def test_wind_45_to_54_over_30k_is_no_travel():
    assert assess(50, 0, 0, 30_001).level == N
    assert assess(45, 0, 0, 45_000).level == N


def test_wind_45_to_54_at_or_under_30k_stays_severe():
    a = assess(50, 0, 0, 30_000)  # rule is strictly "> 30,000 lb"
    assert a.level == S
    assert a.load_rule is None


def test_wind_35_to_44_over_40k_is_severe():
    a = assess(40, 0, 0, 40_001)
    assert a.level == S
    assert a.load_rule is not None


def test_wind_35_to_44_at_or_under_40k_stays_high():
    assert assess(40, 0, 0, 40_000).level == H


def test_load_rule_never_lowers_a_worse_hazard():
    # Heavy rain already makes this No Travel; the 35-44 mph "Severe" load rule must not reduce it.
    a = assess(40, 1.5, 0, 45_000)
    assert a.level == N
    assert a.load_rule is None


def test_load_rule_does_not_apply_below_35_mph():
    assert assess(30, 0, 0, 80_000).level == M


def test_values_are_rounded_to_display_precision_before_classifying():
    # 44.96 mph displays as 45.0, so it must be treated as 45 (Severe), not High.
    assert assess(44.96, 0, 0, 10_000).wind_level == S
    # 0.249 in/hr displays as 0.25 -> High.
    assert assess(0, 0.249, 0, 10_000).rain_level == H


def test_reason_names_the_driver():
    assert "wind 38 mph" in assess(38, 0, 0, 10_000).reason
    assert "snow" in assess(0, 0, 2.5, 10_000).reason
    assert assess(0, 0, 0, 0).reason == "Conditions within normal limits"
