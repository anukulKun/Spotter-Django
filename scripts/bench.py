"""Local benchmark; it never calls a network provider."""
from pathlib import Path
import os, sys, json, statistics, time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from pathlib import Path
from routing.providers.osrm import meters_to_miles
from routing.services.planner import Planner
from routing.station_index import clear
from django.core.cache import cache
class FixtureProvider:
    def __init__(self, synthetic=False): self.synthetic=synthetic
    def route(self,start,finish):
        if not self.synthetic:
            r=json.loads(Path('tests/fixtures/osrm_dallas_chicago.json').read_text())['routes'][0]
            return {'distance_miles':meters_to_miles(r['distance']),'duration_hours':r['duration']/3600,'geometry':r['geometry'],'provider':'fixture'}
        import numpy as np
        points=[[float(start.lng+(finish.lng-start.lng)*i/24999),float(start.lat+(finish.lat-start.lat)*i/24999)] for i in range(25000)]
        return {'distance_miles':2800.0,'duration_hours':45.0,'geometry':{'type':'LineString','coordinates':points},'provider':'synthetic'}
def run(label, provider, reps=30):
    values=[]
    for _ in range(reps):
        cache.clear(); clear(); started=time.perf_counter()
        try: body=Planner(provider).plan('Dallas, TX','Chicago, IL',{'geometry':'none'})
        except Exception as exc: print(label,'iteration failed:',type(exc).__name__,exc); continue
        values.append((body['meta'].get('compute_ms',0), time.perf_counter()-started))
    if values:
        xs=[x[0] for x in values]; print(label, 'compute_ms p50/p95', round(statistics.median(xs),2), round(sorted(xs)[int(.95*len(xs))-1],2))
if __name__=='__main__':
    run('Dallas-Chicago',FixtureProvider()); run('Synthetic-2800mi-25000pts',FixtureProvider(True))
