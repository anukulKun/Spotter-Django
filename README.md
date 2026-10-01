# Fuel Route Planner

## What it is

This is a Django API for planning a driving route and its fuel stops. It uses an OSRM route and the supplied station data to choose low-cost purchases while respecting a 500-mile range at 10 mpg. The small `/map/` page is an extra way to inspect a response.

## Run it

Use Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py import_fuel_prices --from-geocoded data/stations_geocoded.csv
python manage.py runserver
```

Edit `NOMINATIM_USER_AGENT` in `.env` before using the free-text geocoder. Replace `your-email` with a contact address you monitor.

## Using the API

```text
GET http://127.0.0.1:8000/api/route/?start=Dallas,TX&finish=Chicago,IL
```

A trimmed response from the committed Dallas-Chicago sample is:

```json
{
  "summary": {
    "total_fuel_cost_usd": 282.17,
    "fuel_paid_at_stations_usd": 136.17,
    "gallons_consumed": 96.63,
    "number_of_stops": 2
  },
  "fuel_stops": [{
    "name": "EXTRA MILE TRUCK STOP",
    "city": "Hooks",
    "state": "TX",
    "mile_marker": 163.13,
    "gallons_purchased": 16.313,
    "cost_usd": 45.96
  }]
}
```

The API also accepts JSON POST requests and returns JSON errors with an `error.code` and `error.message`.

## How it works

1. Endpoint names are resolved from the local gazetteer; an unknown free-text address uses one Nominatim request.
2. OSRM supplies one driving route, and the normalized route is cached.
3. The route is densified and stations are matched to cumulative route miles.
4. Matching tries a 5-mile corridor, then 10 miles, then 15 miles.
5. With a zero stop penalty, the greedy optimizer is the exact reference path.
6. With a positive penalty, long routes use a pruned search over relevant candidates; this is a heuristic and is stated in the response assumptions.
7. Total cost is station fuel paid plus the value of fuel consumed from the starting full tank.

## Assumptions

| Item | Rule |
|---|---|
| Starting tank | The vehicle starts full; fuel consumed from that tank is included in total cost. |
| Duplicate prices | Duplicate rows for a station ID use the median price. |
| Station locations | Imported stations use the city-centroid location. |
| Corridor | The matcher widens from 5 to 10 to 15 miles. |
| Stop penalty | The default is $5 per station purchase. `0` uses the greedy reference path. |
| Detours | Corridor offset is reported, but detour fuel is not priced separately. |
| MPG and range | Defaults are 10 mpg and 500 miles; both are request parameters within bounds. |

## Data notes

The importer drops Canadian rows and merges duplicate station IDs. `data/manual_geocodes.csv` overrides fuzzy city matches. `data/stations_geocoded.csv` is committed so a fresh clone does not need `US.txt` to run. `scripts/build_gazetteer.py` remains available for rebuilding the city file from GeoNames data. GeoNames data is used under CC BY 4.0.

## Performance

These are measured warm-cache results from this machine using 30 repetitions of `scripts/bench.py`:

| Route | Compute p50 | Compute p95 | Routing p95 |
|---|---:|---:|---:|
| Dallas to Chicago | 29.13 ms | 30.23 ms | 0 ms on cache hit |
| Los Angeles to New York | 46.55 ms | 50.32 ms | 0 ms on cache hit |
| Seattle to Miami | 47.44 ms | 48.41 ms | 0 ms on cache hit |

A full response-cache hit reports `meta.external_calls: 0` and `meta.osrm_ms: 0`. A provider route-cache miss reports one external routing call. The benchmark uses saved OSRM fixtures, so its routing time is not a live-provider latency measurement.

## Errors

| Code | Meaning |
|---|---|
| `INVALID_PARAMS` | A required value is missing or a numeric value is outside its bounds. |
| `LOCATION_NOT_FOUND` | The location could not be resolved. |
| `LOCATION_NOT_SUPPORTED` | The input is not a supported lower-48 city/state or coordinate. |
| `LOCATION_NOT_IN_US` | The location is explicitly outside the US dataset, such as Toronto. |
| `NO_FUEL_STATION_IN_RANGE` | A route gap is longer than the requested range. |
| `NO_ROUTE` | The routing provider found no drivable route. |
| `ROUTING_PROVIDER_ERROR` / `ROUTING_PROVIDER_TIMEOUT` | The routing provider failed or timed out. |

## Tests

Run the offline suite with:

```powershell
pytest -q
python manage.py check
```

The tests use saved OSRM fixtures and do not call public routing services. The penalty oracle generates small station sets, compares the optimizer with every feasible station subset, and checks penalties of 0, 2, 5, and 15. The independent response verifier checks range gaps, tank bounds, conservation, station prices, corridor distance, and rounded costs.

## Limitations

Station coverage is sparse in parts of California and Oregon, so some routes are infeasible at a 500-mile range. Public OSRM is best-effort and may be unavailable or change its response time. The resolver supports the lower 48 states only. `/map/` is a small extra and is not required for using the API.
