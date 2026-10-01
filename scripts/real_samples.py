import os,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django; django.setup()
from django.core.cache import cache
from routing.services.planner import Planner
routes=[('dallas_chicago','Dallas, TX','Chicago, IL',{}),('newyork_miami','New York, NY','Miami, FL',{}),('losangeles_newyork','Los Angeles, CA','New York, NY',{}),('seattle_miami','Seattle, WA','Miami, FL',{}),('losangeles_seattle_gap','Los Angeles, CA','Seattle, WA',{}),('losangeles_seattle_range1000','Los Angeles, CA','Seattle, WA',{'range_miles':1000}),('denver_kansascity','Denver, CO','Kansas City, MO',{}),('dallas_fortworth','Dallas, TX','Fort Worth, TX',{})]
for name,start,finish,params in routes:
 try: body=Planner().plan(start,finish,params); status=200
 except Exception as e:
  from routing.optimizer import InfeasibleRoute
  body={'error':{'code':'NO_FUEL_STATION_IN_RANGE' if isinstance(e,InfeasibleRoute) else type(e).__name__,'message':str(e)}}; status=422 if isinstance(e,InfeasibleRoute) else 500
 out={'http_status':status,**body}; open(f'docs/sample_responses/{name}.json','w',encoding='utf-8').write(json.dumps(out,indent=2))
 print(name,status,body.get('route',{}).get('distance_miles'),len(body.get('fuel_stops',[])),body.get('meta',{}).get('routing_source'),body.get('meta',{}).get('external_calls'))

