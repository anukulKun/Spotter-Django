from pathlib import Path

import requests

url = "https://router.project-osrm.org/route/v1/driving/-96.797,32.7767;-87.6298,41.8781"
r = requests.get(
    url,
    params={"overview": "full", "geometries": "geojson", "steps": "false"},
    headers={"User-Agent": "spotter-fuel-route-assessment"},
    timeout=10,
)
r.raise_for_status()
Path("tests/fixtures").mkdir(parents=True, exist_ok=True)
Path("tests/fixtures/osrm_dallas_chicago.json").write_text(r.text, encoding="utf-8")
print("recorded", len(r.text))
