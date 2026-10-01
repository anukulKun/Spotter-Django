import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from django.core.cache import cache

from routing.services.planner import Planner
from scripts.bench import FixtureProvider

root = Path(__file__).resolve().parents[1]
cache.clear()
body = Planner(FixtureProvider(root / "tests/fixtures/osrm_losangeles_newyork.json")).plan(
    "Los Angeles, CA", "New York, NY", {"geometry": "none", "stop_penalty_usd": 0}
)
print(
    {
        "osrm_ms": body["meta"]["osrm_ms"],
        "compute_ms": body["meta"]["compute_ms"],
        "timings": body["meta"]["timings"],
    }
)
