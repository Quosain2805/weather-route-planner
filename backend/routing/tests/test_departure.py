import json
import re
import time
from urllib.parse import parse_qs, urlparse

import pytest
import responses
from rest_framework.test import APIClient

from routing.domain.departure import DepartureOption, best_offset, explain
from routing.domain.ranking import RouteStats
from routing.domain.risk import Risk
from routing.tests.test_api import METEO, OSRM, departure, osrm_callback, payload


def option(offset, minutes=600, **miles):
    full = {lvl: 0.0 for lvl in Risk}
    full[Risk.LOW] = 1000.0
    for name, value in miles.items():
        full[Risk[name.upper()]] = value
    return DepartureOption(offset, RouteStats("r1", minutes * 60, full))


def test_leaving_now_when_it_is_already_the_best():
    options = [option(0), option(1), option(2)]
    assert best_offset(options) == 0
    assert "looks good" in explain(options, 0)


def test_trivial_improvements_are_not_worth_a_delay():
    # Moderate-only weather clearing, or a few Severe miles, must not make a driver wait hours.
    assert best_offset([option(0, moderate=120), option(8)]) == 0
    assert best_offset([option(0, severe=6), option(5)]) == 0
    assert best_offset([option(0, high=20), option(5)]) == 0
    assert best_offset([option(0, severe=12), option(5)]) == 5     # 12 fewer Severe miles is worth it
    assert best_offset([option(0, high=30), option(5)]) == 5


def test_waits_for_a_storm_to_pass_and_picks_the_earliest_good_hour():
    options = [option(0, severe=80), option(1, severe=80), option(2, severe=40), option(3), option(4), option(5)]
    assert best_offset(options) == 3          # earliest clean start, not the last one
    assert explain(options, 3) == "Leave 3 hours later and Severe miles fall from 80 to 0."


def test_no_travel_improvement_is_reported_first():
    options = [option(0, no_travel=60, severe=30), option(1, severe=30)]
    assert best_offset(options) == 1
    assert "No Travel miles fall from 60 to 0" in explain(options, 1)


def test_does_not_suggest_waiting_when_no_better_window_exists():
    options = [option(0, high=50), option(1, high=50), option(2, high=70)]
    assert best_offset(options) == 0
    assert "No meaningfully better start time" in explain(options, 0)


def test_ignores_improvements_beyond_the_maximum_delay():
    options = [option(0, severe=80)] + [option(h, severe=80) for h in range(1, 30)] + [option(30)]
    assert best_offset(options) == 0          # a clean start 30 h out is too long to ask a driver to wait


def test_singular_hour_wording():
    options = [option(0, high=40), option(1)]
    assert explain(options, 1).startswith("Leave 1 hour later")


def test_empty_options_are_safe():
    assert best_offset([]) == 0
    assert explain([], 0)


# ---- end to end: a storm that passes ----------------------------------------------------------

def passing_storm_callback(request):
    """Every location is in a No Travel gale for the first ~5 hours from now, then calm."""
    q = parse_qs(urlparse(request.url).query)
    n = len(q["latitude"][0].split(","))
    now_hour = int(time.time()) // 3600 * 3600
    times = [now_hour - 86_400 + i * 3600 for i in range(14 * 24)]
    wind = [60.0 if now_hour <= t <= now_hour + 5 * 3600 else 8.0 for t in times]
    loc = {
        "timezone": "America/Chicago",
        "utc_offset_seconds": -21600,
        "hourly": {
            "time": times,
            "wind_speed_10m": wind,
            "rain": [0.0] * len(times),
            "showers": [0.0] * len(times),
            "snowfall": [0.0] * len(times),
        },
    }
    out = [loc] * n
    return 200, {}, json.dumps(out if n > 1 else out[0])


@pytest.fixture
def storm():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_callback(responses.GET, OSRM, callback=osrm_callback, content_type="application/json")
        rsps.add_callback(responses.GET, METEO, callback=passing_storm_callback, content_type="application/json")
        yield rsps


def test_api_recommends_waiting_out_a_passing_storm(storm):
    res = APIClient().post("/api/analyze", payload(departure=departure(1)), format="json")
    assert res.status_code == 200, res.content
    plan = res.json()["departure_plan"]

    options = plan["options"]
    assert options[0]["offset_h"] == 0 and len(options) == 49
    assert options[0]["max_risk"] == 4                       # leaving into the gale
    assert options[-1]["max_risk"] == 0                      # two days later: calm
    assert [o["epoch"] for o in options] == sorted(o["epoch"] for o in options)

    chosen = plan["recommended_offset_h"]
    assert 3 <= chosen <= 7                                  # right after the storm clears
    assert options[chosen]["max_risk"] == 0
    assert options[chosen - 1]["max_risk"] > 0               # and not a minute later than needed
    assert "later" in plan["message"] and "No Travel" in plan["message"]


def test_plan_never_offers_departures_the_api_would_refuse(storm):
    seven_days_out = departure(24 * 7 - 5)
    plan = APIClient().post("/api/analyze", payload(departure=seven_days_out), format="json").json()["departure_plan"]
    assert len(plan["options"]) <= 6                          # only ~5 hours left before the 7-day limit
    assert plan["recommended_offset_h"] <= len(plan["options"]) - 1
