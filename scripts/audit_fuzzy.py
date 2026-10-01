import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import difflib
from pathlib import Path

import django

django.setup()
from routing.geo import haversine_miles
from routing.management.commands.import_fuel_prices import load_gazetteer, normalize_city
from routing.models import FuelStation

g = load_gazetteer(Path("data/us_cities.csv"))
for x in FuelStation.objects.filter(geocode_quality="fuzzy").order_by("city", "state"):
    names = [n for n, s in g if s == x.state]
    m = difflib.get_close_matches(normalize_city(x.city), names, n=1, cutoff=0.9)[0]
    v = g[(m, x.state)]
    miles = float(haversine_miles(x.latitude, x.longitude, v[0], v[1]))
    print(
        f"{x.city}, {x.state} -> {v[3]}, {x.state} | {miles:.1f} miles | "
        + ("FLAG >15" if miles > 15 else "ok")
    )
