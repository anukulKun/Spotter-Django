from pathlib import Path
import cProfile,pstats,io,os,sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django; django.setup(); import config.wsgi
from django.core.cache import cache
from routing.services.planner import Planner
from routing.station_index import clear
from routing.providers.osrm import meters_to_miles
class Fixture:
    def __init__(self,path): self.path=Path(path)
    def route(self,start,finish):
        r=json.loads(self.path.read_text())['routes'][0]; return {'distance_miles':meters_to_miles(r['distance']),'duration_hours':r['duration']/3600,'geometry':r['geometry'],'provider':'fixture'}
root=Path(__file__).resolve().parents[1]
for name,start,finish,fixture in [('LA-NY','Los Angeles, CA','New York, NY','osrm_losangeles_newyork.json'),('Seattle-Miami','Seattle, WA','Miami, FL','osrm_seattle_miami.json')]:
    cache.clear(); profiler=cProfile.Profile(); profiler.enable(); body=Planner(Fixture(root/'tests/fixtures'/fixture)).plan(start,finish,{'geometry':'none','stop_penalty_usd':0}); profiler.disable(); print(f'{name}: compute_ms={body["meta"]["compute_ms"]} timings={body["meta"]["timings"]}'); stats=pstats.Stats(profiler).sort_stats('cumulative'); stats.print_stats(12)


