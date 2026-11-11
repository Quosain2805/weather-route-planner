"""End-to-end API tests with the routing, weather and geocoding services mocked out."""
import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
import responses
from rest_framework.test import APIClient

OSRM = re.compile(r"https://router\.project-osrm\.org/route/v1/driving/.*")
METEO = re.compile(r"https://api\.open-meteo\.com/v1/forecast.*")

# Three routes west to east, each ~100 mi: south (calm), middle, north (stormy). The northern
# one is the *fastest*, so a recommendation of the southern route proves weather beat speed.
LON_START, LON_END = -90.0, -88.55


def osrm_route(lat, minutes):
    lons = [LON_START + i * (LON_END - LON_START) / 4 for i in range(5)]
    steps = []
    for a, b in zip(lons, lons[1:]):
        steps.append(
            {
                "geometry": {"type": "LineString", "coordinates": [[a, lat], [b, lat]]},
                "duration": minutes * 60 / 4,
                "distance": 25 * 1609.344,
                "name": "I 80",
                "ref": "I 80",
            }
        )
    return {"legs": [{"steps": steps}], "duration": minutes * 60, "distance": 100 * 1609.344}


def osrm_callback(request):
    body = {
        "code": "Ok",
        "routes": [osrm_route(41.0, 100), osrm_route(40.5, 110), osrm_route(40.0, 120)],
    }
    return 200, {}, json.dumps(body)


def meteo_callback(request):
    """Wind depends on latitude: calm in the south, 50 mph in the north."""
    q = parse_qs(urlparse(request.url).query)
    lats = [float(x) for x in q["latitude"][0].split(",")]
    base = int(time.time()) // 3600 * 3600 - 86_400
    times = [base + i * 3600 for i in range(14 * 24)]

    def location(lat):
        wind = 50.0 if lat >= 40.95 else 30.0 if lat >= 40.45 else 8.0
        n = len(times)
        return {
            "timezone": "America/Chicago",
            "utc_offset_seconds": -21600,
            "hourly": {
                "time": times,
                "wind_speed_10m": [wind] * n,
                "rain": [0.0] * n,
                "showers": [0.0] * n,
                "snowfall": [0.0] * n,
            },
        }

    out = [location(lat) for lat in lats]
    return 200, {}, json.dumps(out if len(out) > 1 else out[0])


def departure(hours=2):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def payload(**overrides):
    body = {
        "origin": {"lat": 40.0, "lon": -90.0, "label": "A"},
        "destination": {"lat": 40.0, "lon": -88.55, "label": "B"},
        "departure": departure(),
        "load_lb": 35_000,
        "interval_miles": 25,
    }
    body.update(overrides)
    return body


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def mocked():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_callback(responses.GET, OSRM, callback=osrm_callback, content_type="application/json")
        rsps.add_callback(responses.GET, METEO, callback=meteo_callback, content_type="application/json")
        yield rsps


def test_recommends_calm_route_over_faster_stormy_one(client, mocked):
    res = client.post("/api/analyze", payload(), format="json")
    assert res.status_code == 200, res.content
    data = res.json()

    routes = {r["id"]: r for r in data["routes"]}
    assert len(routes) == 3
    fastest = min(routes.values(), key=lambda r: r["duration_s"])
    best = routes[data["recommended_route_id"]]

    assert fastest["fastest"] and fastest["summary"]["max_risk"] == 4          # 50 mph + 35,000 lb
    assert best["duration_s"] == 120 * 60 and best["summary"]["max_risk"] == 0
    assert best["recommended"] and best["rank"] == 1
    assert [r["rank"] for r in data["routes"]] == [1, 2, 3]
    # The runner-up is the moderate-wind route, so average risk is what separates them.
    assert "Lowest average weather risk" in best["reasons"][0]


def test_checkpoints_cover_the_route_and_carry_eta(client, mocked):
    data = client.post("/api/analyze", payload(), format="json").json()
    for route in data["routes"]:
        cps = route["checkpoints"]
        assert cps[0]["mile"] == 0 and cps[-1]["mile"] == pytest.approx(route["distance_mi"], abs=0.2)
        assert sum(c["covered_miles"] for c in cps) == pytest.approx(route["distance_mi"], abs=0.5)
        assert sum(route["summary"]["miles_by_risk"].values()) == pytest.approx(route["distance_mi"], abs=0.5)
        etas = [c["eta_epoch"] for c in cps]
        assert etas == sorted(etas)
        assert cps[0]["eta_epoch"] == route["departure_epoch"]
        assert cps[0]["timezone"] == "America/Chicago"


def test_load_changes_the_outcome(client, mocked):
    """The same 50 mph wind is No Travel at 35,000 lb but only Severe at 20,000 lb."""
    light = client.post("/api/analyze", payload(load_lb=20_000), format="json").json()
    north = min(light["routes"], key=lambda r: r["duration_s"])
    assert north["summary"]["max_risk"] == 3


def test_interval_controls_checkpoint_spacing(client, mocked):
    ten = client.post("/api/analyze", payload(interval_miles=10), format="json").json()
    fifty = client.post("/api/analyze", payload(interval_miles=50), format="json").json()
    assert len(ten["routes"][0]["checkpoints"]) > len(fifty["routes"][0]["checkpoints"])
    assert [c["mile"] for c in fifty["routes"][0]["checkpoints"]][:2] == [0, 50]


def test_heatmap_shape_is_slider_ready(client, mocked):
    hm = client.post("/api/analyze", payload(), format="json").json()["heatmap"]
    assert hm["hours"] == 48 and hm["points"]
    for p in hm["points"]:
        assert all(len(p[k]) == 49 for k in ("risk", "wind", "rain", "snow"))
    assert max(max(p["risk"]) for p in hm["points"]) == 4
    assert hm["start_epoch"] % 3600 == 0
    assert hm["scales"]["wind"] == [25, 35, 45, 55]


@pytest.mark.parametrize(
    "change, fragment",
    [
        ({"load_lb": -1}, "load_lb"),
        ({"load_lb": 90_000}, "load_lb"),
        ({"interval_miles": 30}, "Choose one of"),
        ({"departure": "2001-01-01T00:00:00Z"}, "past"),
        ({"departure": departure(24 * 30)}, "7 days"),
        ({"destination": {"lat": 40.0, "lon": -90.0}}, "too close"),
        ({"origin": {"lat": 120, "lon": 0}}, "origin"),
    ],
)
def test_validation_errors(client, mocked, change, fragment):
    res = client.post("/api/analyze", payload(**change), format="json")
    assert res.status_code == 400
    err = res.json()["error"]
    assert err["code"] == "validation_error"
    assert fragment in err["message"]


def test_no_route_is_a_clear_422(client):
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, OSRM, json={"code": "NoRoute", "message": "no"}, status=200)
        res = client.post("/api/analyze", payload(), format="json")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "no_route"


def test_endpoint_snapped_far_from_requested_point_is_no_route(client):
    """OSRM can snap an origin across an ocean; that must be an error, not a silent wrong route."""
    body = {
        "code": "Ok",
        "routes": [osrm_route(40.0, 120)],
        "waypoints": [{"distance": 5_000_000.0}, {"distance": 30.0}],
    }
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, OSRM, json=body)
        res = client.post("/api/analyze", payload(), format="json")
    assert res.status_code == 422
    assert "starting point" in res.json()["error"]["message"]


def test_endpoints_snapped_a_short_distance_are_fine(client, mocked):
    # Normal case: addresses sit tens of metres from the road. (mocked() has no waypoints at all.)
    assert client.post("/api/analyze", payload(), format="json").status_code == 200


def test_weather_outage_is_reported_not_a_500(client):
    with responses.RequestsMock() as rsps:
        rsps.add_callback(responses.GET, OSRM, callback=osrm_callback, content_type="application/json")
        rsps.add(responses.GET, METEO, status=503)
        res = client.post("/api/analyze", payload(), format="json")
    assert res.status_code == 502
    assert res.json()["error"]["code"] == "upstream_unavailable"


def test_geocode_falls_back_to_nominatim(client):
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, re.compile(r"https://photon\.komoot\.io/.*"), status=500)
        rsps.add(
            responses.GET,
            re.compile(r"https://nominatim\.openstreetmap\.org/.*"),
            json=[{"display_name": "Denver, Colorado, USA", "lat": "39.7392", "lon": "-104.9903"}],
        )
        res = client.get("/api/geocode", {"q": "denver"})
    assert res.status_code == 200
    assert res.json() == [{"label": "Denver, Colorado, USA", "lat": 39.7392, "lon": -104.9903}]


def test_geocode_ignores_very_short_queries(client):
    assert client.get("/api/geocode", {"q": "de"}).json() == []
