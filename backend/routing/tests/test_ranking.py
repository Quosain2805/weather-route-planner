from routing.domain.ranking import RouteStats, explain, rank
from routing.domain.risk import Risk


def stats(rid, minutes, **miles):
    full = {lvl: 0.0 for lvl in Risk}
    for name, value in miles.items():
        full[Risk[name.upper()]] = value
    return RouteStats(rid, minutes * 60, full)


def order(*routes):
    return [s.route_id for s in rank(list(routes))]


def test_fewest_severe_miles_beats_everything_but_no_travel():
    a = stats("a", 600, low=900, severe=40)        # fastest but 40 severe miles
    b = stats("b", 700, low=860, high=200)         # slower, no severe miles
    assert order(a, b) == ["b", "a"]


def test_no_travel_route_never_beats_a_driveable_one():
    risky = stats("risky", 500, low=800, no_travel=30)
    safe = stats("safe", 900, low=700, severe=150, high=100)
    assert order(risky, safe) == ["safe", "risky"]


def test_fewer_high_miles_breaks_severe_tie():
    a = stats("a", 600, low=900, high=120)
    b = stats("b", 650, low=960, high=60)
    assert order(a, b) == ["b", "a"]


def test_average_risk_breaks_tie_on_severe_and_high():
    a = stats("a", 600, low=800, moderate=200)
    b = stats("b", 700, low=950, moderate=50)
    assert order(a, b) == ["b", "a"]


def test_shortest_time_is_last_resort():
    a = stats("a", 700, low=1000)
    b = stats("b", 650, low=1000)
    assert order(a, b) == ["b", "a"]


def test_sub_mile_noise_does_not_override_later_criteria():
    # 0.4 mi of extra Severe is sampling noise: compared at whole-mile resolution it's a tie.
    a = stats("a", 600, low=999.6, severe=0.4)
    b = stats("b", 700, low=1000.0)
    assert order(a, b) == ["a", "b"]


def test_avg_risk_is_mile_weighted():
    s = stats("a", 600, low=75, high=25)
    assert s.avg_risk == 0.5
    assert s.max_risk == Risk.HIGH


def test_explain_names_the_deciding_criterion():
    best = stats("b", 700, low=860, high=200)
    other = stats("a", 600, low=900, severe=40)
    text = explain(best, [other], {"a": "Route 1", "b": "Route 2"})[0]
    assert "Fewest Severe miles" in text and "Route 1" in text


def test_explain_warns_when_every_route_has_no_travel_miles():
    best = stats("b", 700, low=900, no_travel=20)
    other = stats("a", 600, low=800, no_travel=120)
    reasons = explain(best, [other], {"a": "Route 1", "b": "Route 2"})
    assert any("No Travel" in r and "every option" in r for r in reasons)
