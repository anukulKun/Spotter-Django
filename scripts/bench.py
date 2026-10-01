"""Offline p50/p95 benchmark for each long-route fixture."""
from pathlib import Path
import os,sys,json,statistics
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django; django.setup()
from django.core.cache import cache
from routing.providers.osrm import meters_to_miles
from routing.services.planner import Planner
from routing.station_index import clear
class FixtureProvider:
    def __init__(self,path): self.path=Path(path)
    def route(self,start,finish):
        r=json.loads(self.path.read_text(encoding='utf-8'))['routes'][0]
        return {'distance_miles':meters_to_miles(r['distance']),'duration_hours':r['duration']/3600,'geometry':r['geometry'],'provider':'fixture'}
def p95(xs): return sorted(xs)[max(0,int(.95*len(xs))-1)]
def run(label,provider,start,finish,reps=30):
    values=[]
    for _ in range(reps):
        cache.clear(); body=Planner(provider).plan(start,finish,{'geometry':'none','stop_penalty_usd':0}); timings=dict(body['meta']['timings']); timings['_compute_ms']=body['meta']['compute_ms']; values.append(timings)
    print(label)
    compute=[v['_compute_ms'] for v in values]
    print(f'  compute_ms: p50={statistics.median(compute):.2f} ms p95={p95(compute):.2f} ms')
    for stage in ['resolve_endpoints_ms','route_prep_ms','corridor_match_ms','optimizer_ms','response_build_ms']:
        xs=[v.get(stage,0) for v in values]; print(f'  {stage}: p50={statistics.median(xs):.2f} ms p95={p95(xs):.2f} ms')
def cold(label,provider,start,finish):
    cache.clear(); clear(); body=Planner(provider).plan(start,finish,{'geometry':'none','stop_penalty_usd':0}); print(f'{label} cold: osrm_ms={body["meta"]["osrm_ms"]:.2f} compute_ms={body["meta"]["compute_ms"]:.2f}')
if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    run('Dallas-Chicago',FixtureProvider(root/'tests/fixtures/osrm_dallas_chicago.json'),'Dallas, TX','Chicago, IL')
    run('Los-Angeles-New-York',FixtureProvider(root/'tests/fixtures/osrm_losangeles_newyork.json'),'Los Angeles, CA','New York, NY')
    run('Seattle-Miami',FixtureProvider(root/'tests/fixtures/osrm_seattle_miami.json'),'Seattle, WA','Miami, FL')
    cold('LA-NY',FixtureProvider(root/'tests/fixtures/osrm_losangeles_newyork.json'),'Los Angeles, CA','New York, NY')
    cold('Seattle-Miami',FixtureProvider(root/'tests/fixtures/osrm_seattle_miami.json'),'Seattle, WA','Miami, FL')

