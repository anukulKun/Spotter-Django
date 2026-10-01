import os,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django; django.setup()
import requests
from routing.providers.geocode import resolve_location
from django.conf import settings
routes=[('losangeles_newyork','Los Angeles, CA','New York, NY'),('seattle_miami','Seattle, WA','Miami, FL')]
for name,start_text,finish_text in routes:
    calls=[0]; start=resolve_location(start_text,calls); finish=resolve_location(finish_text,calls)
    url=f"{settings.OSRM_BASE_URL.rstrip('/')}/route/v1/driving/{start.point.lng},{start.point.lat};{finish.point.lng},{finish.point.lat}"
    response=requests.get(url,params={'overview':'full','geometries':'geojson','steps':'false'},headers={'User-Agent':settings.NOMINATIM_USER_AGENT},timeout=10); response.raise_for_status()
    Path(f'tests/fixtures/osrm_{name}.json').write_text(json.dumps(response.json(),indent=2),encoding='utf-8')
    print(name,response.status_code,len(response.content))
