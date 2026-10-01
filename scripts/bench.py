"""Offline benchmark with per-stage p50/p95 timings."""
from pathlib import Path
import os,sys,json,statistics,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django; django.setup()
from django.core.cache import cache
from routing.providers.osrm import meters_to_miles
from routing.services.planner import Planner
from routing.station_index import clear
class FixtureProvider:
 def route(self,start,finish):
  r=json.loads(Path('tests/fixtures/osrm_dallas_chicago.json').read_text())['routes'][0]; return {'distance_miles':meters_to_miles(r['distance']),'duration_hours':r['duration']/3600,'geometry':r['geometry'],'provider':'fixture'}
def p95(xs): return sorted(xs)[max(0,int(.95*len(xs))-1)]
def run(label,provider,reps=30):
 values=[]
 for _ in range(reps):
  cache.clear(); clear(); body=Planner(provider).plan('Dallas, TX','Chicago, IL',{'geometry':'none','stop_penalty_usd':0}); values.append(body['meta']['timings'])
 stages=['resolve_endpoints_ms','route_prep_ms','corridor_match_ms','optimizer_ms','response_build_ms']
 print(label)
 for stage in stages:
  xs=[v.get(stage,0) for v in values]; print(f'  {stage}: p50={statistics.median(xs):.2f} ms p95={p95(xs):.2f} ms')
if __name__=='__main__': run('Dallas-Chicago',FixtureProvider())

