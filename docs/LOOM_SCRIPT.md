# Loom script (5 minutes)

1. Start with Postman and show the four successful route requests: Dallas-Chicago, New York-Miami, Los Angeles-New York, and Seattle-Miami.
2. Point out the JSON envelope: resolved endpoints, GeoJSON route, fuel stops, full-trip fuel cost, assumptions, and timings.
3. Show the Los Angeles-Seattle 422 gap response, then run the `range_miles=1000` retry.
4. In a short bonus segment, open the map URL and submit another route; show the route, numbered stops, and raw JSON link.
5. Tour `routing/management/commands/import_fuel_prices.py`, `routing/optimizer.py`, `tests/test_penalty_oracle.py`, `routing/services/planner.py`, and `scripts/verify_response.py`.
6. Finish with `pytest -q` and explain that the suite is offline and independently checks fuel conservation and cost fields.

Use the exact requests named in `docs/postman_collection.json`: Dallas-Chicago, New York-Miami, Los Angeles-New York, Seattle-Miami, LA-Seattle gap, LA-Seattle range 1000, Missing params, Toronto, and POST example.
