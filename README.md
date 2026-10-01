# Fuel Route Planner

A Django API that plans fuel stops on real driving routes, accounting for a full starting tank, station prices, range, corridor matching, and a configurable stop penalty. The map page is a small bonus.

## Quick start (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py import_fuel_prices --from-geocoded data/stations_geocoded.csv
python manage.py runserver
```

Then request:

```text
http://127.0.0.1:8000/api/route/?start=Dallas,TX&finish=Chicago,IL
```

The committed Dallas-Chicago sample has a 966.30-mile route, two stops, and a full-trip total fuel cost of $282.17 at the default $5 stop penalty. See `docs/sample_responses/dallas_chicago.json` for the complete response.

## Docker

```powershell
docker compose up --build
```

The image runs migrations, imports `data/stations_geocoded.csv` when the station table is empty, and serves Gunicorn. SQLite is the default outside Docker; Compose uses PostgreSQL. Redis is available under the `redis` profile.

## How it works

1. Resolve each endpoint through the local city gazetteer, then one bounded Nominatim fallback.
2. Fetch or reuse an OSRM driving route.
3. Densify the route and compute cumulative route miles.
4. Match stations inside the 5/10/15-mile corridor policy.
5. Plan purchases with a greedy zero-penalty path or the penalty optimizer.
6. Return JSON with fuel conservation, costs, assumptions, and timings.

## Requirement -> file traceability

| Requirement | Evidence |
|---|---|
| City/state and coordinate inputs | `routing/providers/geocode.py` |
| Full state names | `routing/providers/geocode.py` |
| Manual geocode overrides | `data/manual_geocodes.csv`, `routing/providers/geocode.py` |
| OSRM routing and cache | `routing/providers/osrm.py`, `routing/services/planner.py` |
| Station import and duplicate median | `routing/management/commands/import_fuel_prices.py` |
| Corridor matching | `routing/corridor.py`, `routing/services/planner.py` |
| Range-safe fuel planning | `routing/optimizer.py` |
| Stop penalty | `routing/optimizer.py`, `config/settings.py` |
| JSON API and error contract | `routing/views.py`, `routing/renderers.py` |
| Independent verification | `scripts/verify_response.py`, `tests/test_verify_response.py` |
| API samples/Postman | `docs/sample_responses/`, `docs/postman_collection.json` |
| Map bonus | `templates/routing/map.html`, `routing/static/routing/map.js` |
| Test suite and offline CI | `tests/`, `.github/workflows/tests.yml` |

## Assumptions

| Assumption | Rule |
|---|---|
| Starting fuel | Vehicle starts with a full tank. |
| Price rule | Median of duplicate price rows per station ID. |
| Station locations | City-centroid geocodes from the importer. |
| Corridor | Automatically tries 5, then 10, then 15 miles. |
| Stop penalty | Default $5.00 per station purchase; `0` keeps the pure greedy fast path. |
| Total cost | Rounded station purchases plus consumed starting-tank fuel at the average purchase price, or corridor median when there are no purchases. |
| Detours | Corridor offset is reported; detour fuel is not separately priced. |

## Data handling

Canadian rows are dropped, duplicate station IDs are merged, and manual geocodes override fuzzy matches. The committed `stations_geocoded.csv` is used by fresh clones. The GeoNames build script is `scripts/build_gazetteer.py`; the source data is used under GeoNames CC BY 4.0 terms.

## Optimality and performance

The finite-breakpoint penalty oracle test checked 7,632 generated cases across penalties 0, 2, 5, and 15 with zero mismatches. The long-route penalty path prunes to greedy-selected candidates for performance, so that result is not a proof of global optimality for arbitrary large candidate sets; the zero-penalty path is the exact greedy reference.

Warm cache-hit benchmark results from `scripts/bench.py` (30 repetitions) were:

| Route | compute p50 | compute p95 | resolve p95 | corridor p95 |
|---|---:|---:|---:|---:|
| Dallas-Chicago | 29.13 ms | 30.23 ms | 18.68 ms | 3.98 ms |
| Los Angeles-New York | 46.55 ms | 50.32 ms | 18.98 ms | 10.55 ms |
| Seattle-Miami | 47.44 ms | 48.41 ms | 18.90 ms | 11.88 ms |

`osrm_ms` is 0 on a route-cache hit and `meta.external_calls` is 0 on a full response-cache hit; a provider miss reports one external call.

## Error contract

Errors are JSON objects with `error.code` and `error.message`; infeasible routes also include gap details and a suggestion. `INVALID_PARAMS` and `LOCATION_NOT_SUPPORTED` are 400 responses, `NO_FUEL_STATION_IN_RANGE` is 422, and provider failures use 502/504.

## Testing

Run `pytest -q` and `python manage.py check`. Tests use fixtures and do not call the public routing provider.

## Known limitations and future work

Station coverage is sparse in parts of California and Oregon, so some west-coast routes are infeasible at 500 miles. Public OSRM is best-effort. The frontend is not required; `/map/` is a small bonus. Future work could add a managed routing provider, richer station coverage, and a globally exact large-route penalty optimizer.

