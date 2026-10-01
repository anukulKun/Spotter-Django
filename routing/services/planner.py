from __future__ import annotations
import hashlib,json,time
import numpy as np
from django.conf import settings
from django.core.cache import cache
from routing.corridor import match_corridor
from routing.geo import cumulative_miles,densify
from routing.optimizer import Candidate,InfeasibleRoute,plan_refuelling
from routing.providers.base import NoRouteError,RoutingProviderError,RoutingTimeout
from routing.providers.geocode import resolve_location
from routing.providers.osrm import default_provider
from routing.station_index import stations
from routing.models import ImportRun

def data_version():
    x=ImportRun.objects.order_by('-created_at').first(); return x.data_version if x else 'empty'
def key(prefix,value): return prefix+hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
def simplify(coords,tolerance=.01):
    if len(coords)<=2:return coords
    keep=[0]; a=np.asarray(coords,float)
    for i in range(1,len(a)-1):
        if np.linalg.norm(a[i]-a[keep[-1]])>=tolerance: keep.append(i)
    keep.append(len(a)-1); return [coords[i] for i in keep]
class Planner:
    def __init__(self,provider=None): self.provider=provider or default_provider()
    def plan(self,start_text,finish_text,params=None):
        params=params or {}; started=time.perf_counter(); external=[0]; start=resolve_location(start_text,external); finish=resolve_location(finish_text,external)
        rng=float(params.get('range_miles',getattr(settings,'DEFAULT_RANGE_MILES',500))); mpg=float(params.get('mpg',getattr(settings,'DEFAULT_MPG',10))); corridor=float(params.get('corridor_miles',getattr(settings,'DEFAULT_CORRIDOR_MILES',5))); geometry=params.get('geometry','simplified'); start_fuel=float(params.get('starting_fuel_gallons',0 if mpg == 0 else rng/mpg)); version=data_version()
        if not 50<=rng<=1500 or not 1<=mpg<=50 or not 0<=start_fuel<=rng/mpg or not 1<=corridor<=15 or geometry not in {'simplified','full','none'}: raise ValueError('Invalid route parameters')
        full_key=key('route:',{'s':start_text.casefold().strip(),'f':finish_text.casefold().strip(),'range':rng,'mpg':mpg,'start_fuel':start_fuel,'corridor':corridor,'geometry':geometry,'version':version})
        cached=cache.get(full_key)
        if cached:
            cached['meta']['cache']='hit'; cached['meta']['osrm_ms']=0.0; cached['meta']['compute_ms']=round((time.perf_counter()-started)*1000,2); cached['meta']['total_ms']=round((time.perf_counter()-started)*1000,2); return cached
        route_key=key('routing:',{'s':round(start.point.lat,3),'sl':round(start.point.lng,3),'f':round(finish.point.lat,3),'fl':round(finish.point.lng,3)})
        route=cache.get(route_key); route_cache_hit=route is not None; osrm_started=time.perf_counter()
        if route is None: route=self.provider.route(start.point,finish.point); cache.set(route_key,route,7*86400)
        osrm_ms=0.0 if route_cache_hit else round((time.perf_counter()-osrm_started)*1000,2)
        coords=route['geometry']['coordinates']; raw_lat=np.array([p[1] for p in coords]); raw_lon=np.array([p[0] for p in coords]); lat,lon=densify(raw_lat,raw_lon,1); total=route['distance_miles']; cum=cumulative_miles(lat,lon,total)
        rows=stations()
        if not rows: raise LookupError('Fuel data not loaded')
        candidates=[]; used=coridor=0
        for radius in [corridor,10.0,15.0]:
            hits=match_corridor(lat,lon,cum,np.array([x['latitude'] for x in rows]),np.array([x['longitude'] for x in rows]),np.array([x['opis_id'] for x in rows]),np.array([float(x['price_usd_per_gallon']) for x in rows]),radius)
            try: plan=plan_refuelling([Candidate(h.station_id,h.mile,h.price) for h in hits],total,rng,mpg,start_fuel); candidates,hits_used,used=hits,hits,radius; break
            except InfeasibleRoute as exc: last=exc
        else: raise last
        by_id={x['opis_id']:x for x in rows}; stops=[]
        for i,p in enumerate(plan.purchases,1):
            row=by_id[p.station_id]; cost=round(p.cost,2); stops.append({'order':i,'station_id':p.station_id,'name':row['name'],'address':row['address'],'city':row['city'],'state':row['state'],'lat':row['latitude'],'lng':row['longitude'],'mile_marker':round(p.mile,2),'distance_from_route_miles':round(next(h.offset_miles for h in hits_used if h.station_id==p.station_id),2),'price_per_gallon_usd':round(p.price,3),'arrival_fuel_gallons':round(p.arrival_gallons,3),'gallons_purchased':round(p.gallons,3),'cost_usd':cost,'reason':p.reason})
        prices=[h.price for h in hits_used]; avg=round(sum(s['cost_usd'] for s in stops)/sum(s['gallons_purchased'] for s in stops),3) if stops else (round(float(np.median(prices)),3) if prices else None); basis='purchases' if stops else ('corridor median' if prices else None); geom=None if geometry=='none' else {'type':'LineString','coordinates':coords if geometry=='full' else simplify(coords)}
        response={'start':{'input':start_text,'resolved':start.resolved,'lat':start.point.lat,'lng':start.point.lng,'source':start.source},'finish':{'input':finish_text,'resolved':finish.resolved,'lat':finish.point.lat,'lng':finish.point.lng,'source':finish.source},'route':{'distance_miles':round(total,2),'duration_hours':round(route.get('duration_hours',0),2),'geometry':geom,'geometry_points':len(geom['coordinates']) if geom else 0,'provider':route.get('provider','osrm')},'vehicle':{'range_miles':rng,'mpg':mpg,'tank_gallons':rng/mpg,'starting_fuel_gallons':start_fuel},'fuel_stops':stops,'summary':{'total_fuel_cost_usd':round(sum(s['cost_usd'] for s in stops),2),'gallons_purchased':round(plan.gallons_purchased,3),'gallons_consumed':round(plan.gallons_consumed,3),'ending_fuel_gallons':round(plan.ending_gallons,3),'average_price_paid_per_gallon_usd':avg,'number_of_stops':len(stops),'estimated_trip_fuel_cost_usd':round(plan.gallons_consumed*avg,2) if avg is not None else None,'estimated_trip_cost_basis':basis},'map_url':f'/map/?start={start_text}&finish={finish_text}','assumptions':{'starting_fuel':'Vehicle starts with a full tank; fuel already in the tank is not billed.','price_rule':'median of duplicate CSV rows per station ID','station_locations':'approximate: city centroid','corridor_miles':corridor,'detours':'Stations within the corridor are treated as on-route; detour miles are not charged.'},'meta':{'external_calls':external[0]+1,'cache':'miss','osrm_ms':osrm_ms,'compute_ms':round((time.perf_counter()-started)*1000-osrm_ms,2),'total_ms':round((time.perf_counter()-started)*1000,2),'corridor_miles_used':used,'data_version':version}}
        cache.set(full_key,response,86400); return response
