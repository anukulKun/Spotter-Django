from pathlib import Path
import json
import pytest
from rest_framework.test import APIClient
from routing.models import FuelStation,ImportRun
from routing.providers.base import NoRouteError,RoutingProviderError,RoutingTimeout
from routing.providers.osrm import meters_to_miles
from routing.services.planner import Planner
from routing.station_index import clear
from routing.views import RouteView
class FakeProvider:
    calls=0
    def route(self,start,finish):
        self.calls+=1; p=json.loads(Path('tests/fixtures/osrm_dallas_chicago.json').read_text()); r=p['routes'][0]; return {'distance_miles':meters_to_miles(r['distance']),'duration_hours':r['duration']/3600,'geometry':r['geometry'],'provider':'fixture'}
@pytest.fixture
def api(db):
    p=json.loads(Path('tests/fixtures/osrm_dallas_chicago.json').read_text()); coords=p['routes'][0]['geometry']['coordinates']; picks=[(1001,coords[len(coords)//3]),(1002,coords[len(coords)*2//3])]
    for ident,(lng,lat) in picks: FuelStation.objects.create(opis_id=ident,name='Test Station',address='Exit',city='Test',state='TX',latitude=lat,longitude=lng,price_usd_per_gallon=3.2,price_min=3.2,price_max=3.2)
    ImportRun.objects.create(data_version='test',source_name='fixture'); clear(); RouteView.planner_factory=staticmethod(lambda:Planner(FakeProvider())); from django.core.cache import cache; cache.clear(); return APIClient()
def test_normalization():
    from routing.providers.geocode import normalize_city
    assert normalize_city('St. Louis')==normalize_city('Saint Louis')
    assert normalize_city('Mt. Pleasant')==normalize_city('Mount Pleasant')
def test_happy_cache_and_schema(api):
    first=api.get('/api/route/',{'start':'Dallas, TX','finish':'Chicago, IL'}); assert first.status_code==200; body=first.json(); assert {'start','finish','route','vehicle','fuel_stops','summary','assumptions','meta'}<=body.keys(); assert body['meta']['external_calls']==1
    second=api.get('/api/route/',{'start':'Dallas, TX','finish':'Chicago, IL'}); assert second.status_code==200; assert second.json()['meta']['cache']=='hit'
def test_validation_errors(api):
    assert api.get('/api/route/').status_code==400
    assert api.get('/api/route/',{'start':'Toronto, ON','finish':'Chicago, IL'}).status_code==400
    assert api.get('/api/route/',{'start':'32,-150','finish':'Chicago, IL'}).status_code==400
    assert api.get('/api/route/',{'start':'Dallas, TX','finish':'Chicago, IL','mpg':100}).status_code==400
