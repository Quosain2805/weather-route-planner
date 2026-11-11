"""Development-only stand-in for the Open-Meteo forecast API.

Real forecasts are often calm, which makes it hard to see how the risk rules, route ranking and
heatmap respond to bad weather. This serves the same response shape with a synthetic storm: a
cell that sweeps west to east over about 48 hours, with heavy snow on its northern flank and
heavy rain on its southern one.

    python scripts/mock_weather.py              # listens on :9099
    OPEN_METEO_URL=http://localhost:9099/v1/forecast python manage.py runserver

Nothing here is used in production.
"""
from __future__ import annotations

import json
import math
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 9099
CELL_START_LON = -112.0
CELL_LAT = 41.0
CELL_SPEED_DEG_PER_H = 0.5      # ~27 mph at 40N
RADIUS_MI = 170.0
PAST_HOURS, FUTURE_HOURS = 24, 12 * 24


def miles(lat1, lon1, lat2, lon2):
    dy = (lat2 - lat1) * 69.0
    dx = (lon2 - lon1) * 69.0 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def conditions(lat, lon, hours_from_now):
    center_lon = CELL_START_LON + CELL_SPEED_DEG_PER_H * hours_from_now
    intensity = max(0.0, 1 - miles(lat, lon, CELL_LAT, center_lon) / RADIUS_MI)
    wind = 9 + 50 * intensity**1.1
    northern = lat > CELL_LAT + 0.4
    rain = 0.0 if northern else 1.2 * intensity**1.4
    snow = 3.4 * intensity**1.4 if northern else 0.0
    return round(wind, 1), round(rain, 3), round(snow, 3)


def location(lat, lon, now_hour):
    times = [now_hour + h * 3600 for h in range(-PAST_HOURS, FUTURE_HOURS)]
    rows = [conditions(lat, lon, h) for h in range(-PAST_HOURS, FUTURE_HOURS)]
    return {
        "latitude": lat,
        "longitude": lon,
        "timezone": "America/Denver" if lon < -102 else "America/Chicago",
        "utc_offset_seconds": -25200 if lon < -102 else -21600,
        "hourly": {
            "time": times,
            "wind_speed_10m": [r[0] for r in rows],
            "rain": [r[1] for r in rows],
            "showers": [0.0] * len(rows),
            "snowfall": [r[2] for r in rows],
        },
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        try:
            lats = [float(x) for x in q["latitude"][0].split(",")]
            lons = [float(x) for x in q["longitude"][0].split(",")]
        except (KeyError, ValueError):
            self.send_response(400)
            self.end_headers()
            return
        now_hour = int(time.time()) // 3600 * 3600
        body = [location(a, b, now_hour) for a, b in zip(lats, lons)]
        payload = json.dumps(body if len(body) > 1 else body[0]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    print(f"Mock Open-Meteo on http://localhost:{port}/v1/forecast")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
