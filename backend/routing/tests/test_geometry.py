import pytest

from routing.domain.forecast import HourlySeries, sample
from routing.domain.geo import haversine_mi, simplify
from routing.domain.path import Path, Step
from routing.domain.sampling import checkpoint_miles, effective_interval, plan_checkpoints

ALLOWED = (10, 25, 50)


def line_steps(n_steps=4, miles_per_step=25.0, seconds_per_step=1500.0):
    """A due-east route along the equator in equal steps (1 deg of longitude ~ 69.17 mi)."""
    deg = miles_per_step / 69.0934
    steps = []
    for i in range(n_steps):
        steps.append(Step([(0.0, i * deg), (0.0, (i + 1) * deg)], seconds_per_step))
    return steps


def test_haversine_known_distance():
    chicago, denver = (41.8781, -87.6298), (39.7392, -104.9903)
    assert haversine_mi(chicago, denver) == pytest.approx(920, abs=10)


def test_path_totals_and_lookup():
    path = Path.from_steps(line_steps())
    assert path.total_miles == pytest.approx(100, rel=1e-3)
    assert path.total_seconds == pytest.approx(6000)
    mid = path.at_mile(50)
    assert mid.seconds == pytest.approx(3000, rel=1e-3)
    assert path.at_mile(-5).mile == 0
    assert path.at_mile(10_000).seconds == pytest.approx(6000)


def test_time_follows_each_steps_own_speed():
    deg = 50 / 69.0934
    slow_then_fast = [
        Step([(0, 0), (0, deg)], 7200),  # 50 mi in 2 h
        Step([(0, deg), (0, 2 * deg)], 3000),  # 50 mi in 50 min
    ]
    path = Path.from_steps(slow_then_fast)
    assert path.at_mile(50).seconds == pytest.approx(7200, rel=1e-3)
    assert path.at_mile(75).seconds == pytest.approx(7200 + 1500, rel=1e-3)


def test_empty_route_rejected():
    with pytest.raises(ValueError):
        Path.from_steps([Step([], 0)])


# ---- sampling -----------------------------------------------------------------------------

def test_checkpoints_include_origin_and_destination():
    assert checkpoint_miles(100, 25) == [0, 25, 50, 75, 100]
    assert checkpoint_miles(110, 25)[-1] == 110


def test_short_route_is_origin_and_destination_only():
    assert checkpoint_miles(7, 25) == [0, 7]


def test_tiny_tail_does_not_create_a_crowded_last_checkpoint():
    miles = checkpoint_miles(101, 25)  # 100 would sit 1 mi from the end
    assert miles == [0, 25, 50, 75, 101]


@pytest.mark.parametrize("total", [3.2, 25, 99.9, 100, 640.4, 1003.1])
@pytest.mark.parametrize("interval", [10, 25, 50])
def test_coverage_tiles_route_exactly(total, interval):
    slots = plan_checkpoints(total, interval)
    assert slots[0].covers_from == 0
    assert slots[-1].covers_to == pytest.approx(total)
    assert sum(s.covered_miles for s in slots) == pytest.approx(total)
    for a, b in zip(slots, slots[1:]):
        assert a.covers_to == pytest.approx(b.covers_from)


def test_effective_interval_keeps_requested_when_it_fits():
    assert effective_interval(1000, 25, ALLOWED, 130) == 25


def test_effective_interval_coarsens_very_long_routes():
    assert effective_interval(2000, 10, ALLOWED, 130) == 25
    assert effective_interval(5000, 10, ALLOWED, 130) == 50
    assert effective_interval(20000, 50, ALLOWED, 130) > 50


# ---- forecast interpolation ---------------------------------------------------------------

def series():
    return HourlySeries(
        times=[0, 3600, 7200],
        wind_mph=[10.0, 30.0, 20.0],
        rain_in_hr=[0.0, 0.2, 0.0],
        snow_in_hr=[0.0, 0.0, 1.0],
        timezone="UTC",
        utc_offset_s=0,
    )


def test_sample_exact_and_between_hours():
    s = series()
    assert sample(s, 3600).wind_mph == 30
    mid = sample(s, 1800)
    assert mid.wind_mph == pytest.approx(20)
    assert mid.rain_in_hr == pytest.approx(0.1)
    assert not mid.outside_forecast


def test_sample_outside_window_is_clamped_and_flagged():
    s = series()
    late = sample(s, 99_999)
    assert late.wind_mph == 20 and late.outside_forecast
    early = sample(s, -10)
    assert early.wind_mph == 10 and early.outside_forecast


def test_simplify_keeps_endpoints_and_drops_collinear_points():
    pts = [(0.0, 0.0), (0.0, 1.0), (0.0, 2.0), (0.0, 3.0)]
    assert simplify(pts, 0.001) == [(0.0, 0.0), (0.0, 3.0)]
    bend = [(0.0, 0.0), (1.0, 1.0), (0.0, 2.0)]
    assert simplify(bend, 0.001) == bend
