# Clearway: Weather-Aware Truck Routing

A React + Django web app that helps a truck driver pick the **safest** route for a trip, not just the fastest. For an origin, destination, departure time and load weight it:

1. fetches **three distinct driving routes**,
2. forecasts **wind, rain and snow at the time the truck will actually be at each checkpoint** (every 10 / 25 / 50 miles),
3. scores each checkpoint with the brief's **risk and load rules**,
4. **recommends** a route, and explains why,
5. shows everything on a map, with a **0 to 48 hour weather heatmap** along the trip corridor,
6. and tells the driver **when to leave**: it re-scores all three routes for every start time in the next 48 hours and, if waiting would clearly help, says so ("Leave 7 hours later and No Travel miles fall from 100 to 0") with a one-click re-plan.

**Live app:** _add the hosted URL here_ &nbsp;·&nbsp; **Walkthrough:** _add the Loom link here_

---

## Contents

- [How it works](#how-it-works)
- [Risk model](#risk-model)
- [Route recommendation](#route-recommendation)
- [Architecture](#architecture)
- [API](#api)
- [Running locally](#running-locally)
- [Tests](#tests)
- [Deployment](#deployment)
- [Design decisions and trade-offs](#design-decisions-and-trade-offs)
- [Known limitations](#known-limitations)

## How it works

```
 Browser (React + Leaflet)                      Django API                           Free public APIs
 ─────────────────────────      POST /api/analyze     ───────────────────────────    ─────────────────
 trip form  ───────────────────────────────────────▶  1. routes   ───────────────▶  OSRM (OpenStreetMap)
 route cards, checkpoint table                         2. place checkpoints by mile
 map + heatmap + forecast slider ◀───────────────────  3. forecast at each ETA ───▶  Open-Meteo
                                                       4. classify risk + load rules
                                                       5. rank + explain
```

**ETAs are real, per checkpoint.** Each routing step carries its own duration, so time-along-route follows the road (highway vs. city) instead of assuming one average speed. The weather for a checkpoint is the forecast *at the moment the truck gets there*, linearly interpolated between the two surrounding forecast hours, in that location's own time zone.

**Three routes, always when they exist.** OSRM's alternatives are used first. If it returns fewer than three, the service re-routes through a waypoint pushed sideways off the fastest route's midpoint and keeps the result only if it is genuinely different (less than 85% shared road) and not a silly detour (under 1.6x the fastest time). If a trip really has fewer distinct options, the UI says so.

**Heatmap and routes can never disagree.** The heatmap's per-hour risk comes from the same `assess()` function and the same load as the route scoring, computed on the server. The browser only colours it.

## Risk model

Thresholds are exactly those in the brief and live in one place: [`backend/routing/domain/risk.py`](backend/routing/domain/risk.py).

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind (mph) | < 25 | 25 to 34 | 35 to 44 | 45 to 54 | ≥ 55 |
| Rain (in/hr) | < 0.10 | 0.10 to 0.25 | 0.25 to 0.50 | 0.50 to 1.00 | > 1.00 |
| Snow (in/hr) | < 0.5 | 0.5 to 1.0 | 1.0 to 2.0 | 2.0 to 3.0 | > 3.0 |

Overall risk at a checkpoint is the **worst** of the three hazards, and then the **load rules** can only raise it:

| Rule | Result |
|---|---|
| Wind ≥ 55 mph, any load | No Travel |
| Wind 45 to 54 mph and load > 30,000 lb | No Travel |
| Wind 35 to 44 mph and load > 40,000 lb | Severe |

**Boundary conventions.** The table's ranges touch (for example "0.10 to 0.25" next to "0.25 to 0.50"), so one rule is applied everywhere and covered by tests:

- A value equal to a lower bound belongs to the **higher** band (35 mph is High, 0.25 in/hr is High).
- No Travel is `≥ 55` for wind but strictly `> 1.00` (rain) and `> 3.0` (snow), as the table is worded, so exactly 1.00 in/hr is still Severe.
- Load rules use strict inequalities ("over 30,000 lb"), so a 30,000 lb load is not caught by the 45 to 54 mph rule.
- Values are rounded to display precision (0.1 mph, 0.01 in/hr) **before** classifying, so what the driver reads is always what was classified.

**Rain** is `rain + showers` from Open-Meteo (convective showers would otherwise be missed). Precipitation is requested directly in inches, and Open-Meteo reports the total over the preceding hour, which is in/hr with no conversion. **Wind** is sustained 10 m wind in mph.

## Best time to leave

Picking a route is half the decision; the other half is *when*. For each start time in the next 48 hours (hourly), the service re-scores every route and keeps the best one, using the same checkpoint scoring as the main analysis with the departure shifted. It costs **no extra weather calls**, since the forecasts already fetched cover those hours. The UI shows the result as a 48-bar strip (colour is the worst weather on the best route if you set off then) and a message.

A delay is a real cost to a driver, so waiting is only recommended for a meaningful gain, within 24 hours, and the *earliest* of equally good start times always wins ([`departure.py`](backend/routing/domain/departure.py)):

- any reduction in No Travel miles, or
- 10 or more fewer Severe miles, or
- 25 or more fewer High miles.

Marginal improvements (for example moderate weather clearing) never trigger advice. Start times beyond the forecast, or beyond the 7-day limit the API accepts, are omitted rather than guessed.

## Route recommendation

Routes are ordered by the brief's preference list, compared lexicographically:

1. fewest **Severe** miles
2. fewest **High** miles
3. lowest **average risk** (mile-weighted, 0 = Low to 4 = No Travel)
4. shortest **travel time**

Two deliberate details (see [`ranking.py`](backend/routing/domain/ranking.py)):

- **No Travel miles rank ahead of everything.** A route you are not allowed to drive must never beat one you are, whatever its Severe or High mileage. If every option crosses No Travel conditions the UI says so.
- **Figures are compared at practical resolution** (whole miles, 0.01 risk, whole minutes) so sub-mile sampling noise on near-identical routes does not decide the order before the later criteria get a say.

Each checkpoint "owns" the road halfway to its neighbours, so the per-risk mileage always sums exactly to the route length.

## Architecture

```
backend/
  config/                  settings (env-driven), urls, wsgi
  routing/
    domain/                pure functions, no I/O: the part worth reading first
      risk.py              thresholds, load rules, assess()
      sampling.py          checkpoint placement + coverage, interval coarsening
      path.py              route geometry with cumulative miles and seconds
      forecast.py          hourly series + interpolation at an ETA
      ranking.py           route stats, ordering, plain-language reasons
      departure.py         best time to leave among the scored start times
      similarity.py        "is this a genuinely different route?"
      geo.py               haversine, bearing, simplification
    services/              everything that talks to the outside world
      osrm.py              routes + via-waypoint top-up
      open_meteo.py        batched, cached forecasts on a shared grid
      geocoding.py         Photon with Nominatim fallback
      analysis.py          orchestrates one trip end to end
    views.py serializers.py exceptions.py
    tests/                 109 tests
  scripts/mock_weather.py  dev-only synthetic storm server
frontend/
  src/api/                 typed client and response types
  src/lib/                 formatting, colour scale, heat helpers (unit-tested)
  src/hooks/               analysis request, debounced place search, animated number
  src/components/          form, route cards, checkpoint table, map, heat canvas, forecast panel
```

The `domain/` layer has no network or framework imports, so the rules the brief is graded on are tested exhaustively without mocks. The `services/` layer is the only code that touches third-party APIs, and the API tests mock it at the HTTP boundary.

## API

`POST /api/analyze`

```json
{
  "origin":      { "lat": 41.8781, "lon": -87.6298, "label": "Chicago, IL" },
  "destination": { "lat": 39.7392, "lon": -104.9903, "label": "Denver, CO" },
  "departure": "2026-11-12T14:00:00Z",
  "load_lb": 42000,
  "interval_miles": 25
}
```

Returns `routes` (ranked; each with distance, duration, ETAs, risk summary, simplified geometry and `checkpoints`), `recommended_route_id`, `departure_plan` (outcome and recommendation for each of the next 48 start times), `warnings`, and `heatmap` (per corridor point, 49 hourly values of risk / wind / rain / snow from departure to +48 h, plus the threshold scales used for colouring).

`GET /api/geocode?q=denver` returns `[{label, lat, lon}]`. `GET /api/health` is the liveness check.

Every error uses one envelope, `{"error": {"code", "message", "fields?"}}`, with sensible statuses: `400` validation, `422` no drivable route, `429` throttled, `502/503` an upstream service is down or rate limiting.

## Running locally

Prerequisites: Python 3.12+ and Node 20+. No API keys are needed.

**Backend** (PowerShell):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:DJANGO_DEBUG = "1"
python manage.py runserver        # http://localhost:8000
```

macOS/Linux: `source .venv/bin/activate` and `DJANGO_DEBUG=1 python manage.py runserver`.

**Frontend** (second terminal):

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173, proxies /api to :8000
```

**Single-process, as in production:** `npm run build`, copy `frontend/dist` to `backend/frontend_dist`, and open the Django server on :8000.

> On locked-down Windows machines, Application Control can block the native binary Rollup normally ships. `package.json` therefore overrides Rollup with its official WebAssembly build. It is behaviourally identical and harmless elsewhere.

### Seeing the rules react to bad weather

Real forecasts are often calm. To watch the risk rules, ranking and heatmap respond to a severe system, run the bundled mock Open-Meteo server (development only) and point the backend at it:

```powershell
python scripts/mock_weather.py                                   # terminal 1, :9099
$env:OPEN_METEO_URL = "http://localhost:9099/v1/forecast"        # terminal 2
python manage.py runserver
```

It serves the real API's response shape with a synthetic storm that sweeps west to east over ~48 h, with heavy snow on its northern flank and heavy rain on its southern. Try **Chicago to Denver** and drag the forecast slider.

## Tests

```bash
cd backend  && pytest            # 109 tests
cd frontend && npm test          # 8 tests
cd frontend && npm run build     # strict TypeScript type-check + production build
```

Backend coverage focuses on what matters most for correctness:

- every band **boundary** for wind, rain and snow, and every load rule on both sides of its threshold
- rounding-before-classifying, and load rules never lowering a worse hazard
- checkpoint placement (including short routes and tiny tails) and the invariant that coverage tiles the route exactly
- ETA interpolation, time-follows-step-speed, forecast clamping
- ranking order, the No-Travel-first rule, and tie-breaking
- end to end through the HTTP API with mocked routing/weather: a faster-but-stormy route is beaten by a slower calm one, load changes the outcome, validation and upstream-failure responses

## Deployment

One container serves both the API and the built React app (WhiteNoise), so there is a single service to host. `Dockerfile` and `render.yaml` are included.

**Render:** New → Blueprint → select this repo. `DJANGO_SECRET_KEY` is generated; the service's hostname is allowed automatically; `/api/health` is the health check. Any host that runs a Dockerfile works the same way (set `DJANGO_SECRET_KEY`, and `DJANGO_ALLOWED_HOSTS` if the platform doesn't provide a hostname variable).

Note that free hosts sleep when idle, so the first request after a pause can take about a minute.

## Design decisions and trade-offs

- **Free, keyless services** (OSRM, Open-Meteo, Photon/Nominatim, Esri tiles) so the project runs anywhere without secrets. Each sits behind one small module, so swapping in a paid or truck-aware provider is a local change (`OSRM_URL`, `OPEN_METEO_URL`, `OPEN_METEO_API_KEY` are already configurable).
- **Rate-limit awareness.** The free weather API allows roughly 5,000 locations an hour, so forecasts are snapped to a 0.1° grid (~7 mi, about the resolution of the underlying models) and cached for 45 minutes. Checkpoints and heatmap points on the same grid cell, including shared road across the three routes, cost one lookup. The heatmap spacing defaults to the default checkpoint spacing so it usually adds none. Requests are batched and fetched in parallel. A per-client throttle protects the upstreams, and a 429 surfaces as a clear message, not a stack trace.
- **Server-side scoring.** The browser never re-implements a risk rule. That keeps one source of truth and makes the rules testable without a UI.
- **Stateless service.** No database: results are a pure function of the request plus live forecasts.
- **Very long trips** get a coarser checkpoint interval (and a visible notice) instead of hundreds of weather lookups.
- **Geometry sent to the browser is simplified** (about 170 m tolerance) while distances, mile markers and ETAs use the full-resolution path.
- **Heatmap rendering** is a custom canvas layer rather than a density heat library. Each blob is coloured by its own risk, so one severe cell stays visibly severe instead of being averaged into its neighbours. Radius follows map scale so the corridor stays continuous when zooming, and the slider eases between forecast hours.
- **A dispatch-console interface.** A full-bleed dark map (so the heatmap glows) with floating panels, DOT-amber accents, highway-sign display type (Barlow Condensed) and monospace figures for data. Each route has a *risk profile* chart: one bar per checkpoint, sized by the road it covers and coloured by risk, so you can see where along the trip conditions turn bad (click a bar to jump to that checkpoint). After a search the form folds into a one-line summary so the results are immediately visible.
- **Accessibility:** a real combobox for place search with keyboard navigation, labelled controls, focus states, `aria-live` results, `prefers-reduced-motion` respected.

## Known limitations

- **Routing uses the car profile.** OSRM knows nothing about truck restrictions (height, weight, hazmat) and its speeds are car speeds, so drive times and ETAs are optimistic for a loaded truck. A truck-aware provider is the first thing to swap in.
- **Wind is sustained, not gusts**, matching the brief; gusts would be stricter.
- The public OSRM and Photon servers are demo services with no uptime guarantee; Nominatim is the geocoding fallback.
- **Departure time is entered in the browser's local time zone** (shown under the field); checkpoint ETAs are shown in each checkpoint's own time zone.
- Forecasts reach about 7 days; departures further out are rejected, and any ETA beyond available data is flagged and clamped.
- The in-memory cache is per process, which is fine for one small instance; a shared cache (Redis) would be the next step for scale.

### Ideas for next steps

Truck-specific routing, NWS alerts layered in, saved/shareable trips, and gust-aware rules.
