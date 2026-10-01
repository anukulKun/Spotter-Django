from __future__ import annotations
import csv,difflib,re
from dataclasses import dataclass
from pathlib import Path
import requests
from django.conf import settings
from routing.models import GeocodeCache
from .base import GeoPoint
LOWER_48=(24.0,49.5,-125.0,-66.0)
def normalize_city(v:str)->str:
    v=v.casefold().strip(); v=re.sub(r'\b(st)\.?\b','saint',v); v=re.sub(r'\b(ft)\.?\b','fort',v); v=re.sub(r'\b(mt)\.?\b','mount',v); v=re.sub(r'\b(twp|township)\b','',v); return re.sub(r'[^a-z0-9]+',' ',v).strip()
def in_lower_48(lat,lng): return LOWER_48[0]<=lat<=LOWER_48[1] and LOWER_48[2]<=lng<=LOWER_48[3]
class LocationError(Exception):
    code='LOCATION_NOT_FOUND'
class LocationNotInUs(LocationError):
    code='LOCATION_NOT_IN_US'
@dataclass(frozen=True)
class ResolvedLocation:
    point:GeoPoint; resolved:str; source:str
class Gazetteer:
    def __init__(self,path):
        self.entries={}
        with Path(path).open(newline='',encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                k=(normalize_city(r['city']),r['state'].strip().upper()); v=(float(r['lat']),float(r['lng']),int(float(r.get('population') or 0)),r['city'])
                if k not in self.entries or v[2]>self.entries[k][2]: self.entries[k]=v
    def find(self,text):
        p=[x.strip() for x in text.split(',')]; state=p[-1].upper() if len(p)>=2 and len(p[-1])==2 else None; city=','.join(p[:-1]) if state else text
        if state and state not in {k[1] for k in self.entries}: raise LocationNotInUs('The dataset covers the lower 48 states only')
        key=(normalize_city(city),state) if state else None
        if key in self.entries:
            lat,lng,_,name=self.entries[key]; return lat,lng,f'{name}, {state}', 'gazetteer'
        choices=[(k,v) for k,v in self.entries.items() if not state or k[1]==state]; exact=[x for x in choices if x[0][0]==normalize_city(city)]
        if exact: best=max(exact,key=lambda x:x[1][2])
        else:
            matches=difflib.get_close_matches(normalize_city(city),[x[0][0] for x in choices],n=1,cutoff=.9)
            if not matches: raise LocationError('Location was not found in the lower-48 gazetteer')
            best=max((x for x in choices if x[0][0]==matches[0]),key=lambda x:x[1][2])
        (name,st),(lat,lng,_,display)=best; return lat,lng,f'{display}, {st}','gazetteer'
_gazetteer=None
def get_gazetteer():
    global _gazetteer
    if _gazetteer is None: _gazetteer=Gazetteer(Path(settings.BASE_DIR)/'data/us_cities.csv')
    return _gazetteer
def resolve_location(text,external_calls):
    value=text.strip()
    try:
        lat,lng=(float(x.strip()) for x in value.split(','))
        if not in_lower_48(lat,lng): raise LocationNotInUs('The dataset covers the lower 48 states only')
        return ResolvedLocation(GeoPoint(lat,lng),value,'coordinates')
    except ValueError: pass
    try:
        lat,lng,resolved,source=get_gazetteer().find(value); return ResolvedLocation(GeoPoint(lat,lng),resolved,source)
    except LocationNotInUs: raise
    except (LocationError,FileNotFoundError): pass
    query=value+', USA'; key=query.casefold(); cached=GeocodeCache.objects.filter(query_normalized=key).first()
    if cached: return ResolvedLocation(GeoPoint(cached.latitude,cached.longitude),cached.display_name,'nominatim-cache')
    external_calls[0]+=1
    try:
        r=requests.get('https://nominatim.openstreetmap.org/search',params={'q':query,'format':'jsonv2','limit':1,'countrycodes':'us'},headers={'User-Agent':getattr(settings,'NOMINATIM_USER_AGENT','spotter-fuel-route-assessment')},timeout=10); r.raise_for_status(); x=r.json()[0]; lat,lng=float(x['lat']),float(x['lon'])
    except (requests.RequestException,IndexError,KeyError,ValueError) as exc: raise LocationError('Location was not found') from exc
    if not in_lower_48(lat,lng): raise LocationNotInUs('The dataset covers the lower 48 states only')
    display=x.get('display_name',value); GeocodeCache.objects.update_or_create(query_normalized=key,defaults={'latitude':lat,'longitude':lng,'display_name':display}); return ResolvedLocation(GeoPoint(lat,lng),display,'nominatim')
