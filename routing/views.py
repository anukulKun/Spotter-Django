from django.http import JsonResponse, HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services.planner import Planner
from routing.optimizer import InfeasibleRoute
from .providers.base import NoRouteError,RoutingProviderError,RoutingTimeout
from .providers.geocode import LocationError,LocationNotInUs
from .station_index import stations
from routing.models import ImportRun

def error(code,message,http,details=None): return Response({'error':{'code':code,'message':message,**({'details':details} if details else {})}},status=http)
class RouteView(APIView):
    planner_factory=staticmethod(Planner)
    authentication_classes=[]; permission_classes=[]
    def get(self,request): return self.handle(dict(request.query_params))
    def post(self,request): return self.handle(request.data)
    def handle(self,data):
        start=data.get('start'); finish=data.get('finish')
        if isinstance(start,list):start=start[0]
        if isinstance(finish,list):finish=finish[0]
        if not start or not finish:return error('INVALID_PARAMS','start and finish are required',400)
        try:
            params={};
            for k in ['range_miles','mpg','starting_fuel_gallons','corridor_miles','stop_penalty_usd','geometry']:
                value=data.get(k); params[k]=value[0] if isinstance(value,list) else value
                if value is None: params.pop(k,None)
            return Response(self.planner_factory().plan(start,finish,params))
        except LocationNotInUs as exc:return error(exc.code,str(exc),400)
        except LocationError as exc:return error(exc.code,str(exc),400)
        except ValueError as exc:return error('INVALID_PARAMS',str(exc),400)
        except InfeasibleRoute as exc:return error('NO_FUEL_STATION_IN_RANGE',str(exc),422,{'gap_start_mile':exc.gap_start_mile,'gap_end_mile':exc.gap_end_mile,'range_miles':exc.range_miles})
        except LookupError as exc:return error('FUEL_DATA_NOT_LOADED',str(exc),503)
        except NoRouteError as exc:return error('NO_ROUTE',str(exc),422)
        except RoutingTimeout as exc:return error('ROUTING_PROVIDER_TIMEOUT',str(exc),504)
        except RoutingProviderError as exc:return error('ROUTING_PROVIDER_ERROR',str(exc),502)
        except Exception as exc:return error('ROUTING_PROVIDER_ERROR',str(exc),502)
class HealthView(APIView):
    authentication_classes=[]; permission_classes=[]
    def get(self,request):
        count=len(stations()); return Response({'status':'ok','stations_loaded':count,'data_version':(ImportRun.objects.order_by('-created_at').values_list('data_version',flat=True).first() or 'empty')}) if count else error('FUEL_DATA_NOT_LOADED','Fuel data has not been imported',503)
def placeholder(request):
    return HttpResponse('<html><body><h1>Fuel Route API</h1><p>Plan fuel-efficient US trips.</p><a href="/map/?start=Dallas%2C%20TX&finish=Chicago%2C%20IL">Dallas to Chicago</a> <a href="/map/?start=New%20York%2C%20NY&finish=Miami%2C%20FL">New York to Miami</a> <a href="/map/?start=Denver%2C%20CO&finish=Kansas%20City%2C%20MO">Denver to Kansas City</a></body></html>')
def map_view(request):
    return HttpResponse(MAP_HTML)
MAP_HTML = r'''<!doctype html><html><head><meta charset="utf-8"><title>Fuel Route Map</title><link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"><style>body{font:14px sans-serif;margin:0}#map{height:70vh}#panel{padding:12px}.error{background:#fee;color:#900;padding:8px}</style></head><body><div id="panel"><form id="form">Start <input name="start" value="Dallas, TX"> Finish <input name="finish" value="Chicago, IL"> Range <input name="range_miles" type="number"> MPG <input name="mpg" type="number"><button>Plan</button></form><div id="summary"></div></div><div id="map"></div><script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><script>
const map=L.map('map').setView([39,-98],4);L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap'}).addTo(map);const q=new URLSearchParams(location.search);for(const n of ['start','finish','range_miles','mpg'])if(q.has(n))document.querySelector('[name='+n+']').value=q.get(n);async function load(){const s=new URLSearchParams(new FormData(document.querySelector('form')));for(const [k,v] of [...s])if(!v)s.delete(k);const r=await fetch('/api/route/?'+s);const b=await r.json();document.querySelector('.error')?.remove();if(!r.ok){document.querySelector('#summary').innerHTML='<div class=error>'+b.error.code+': '+b.error.message+'</div>';return}const x=b.summary;document.querySelector('#summary').innerHTML=`Distance ${b.route.distance_miles} mi · ${x.number_of_stops} stops · ${x.gallons_consumed} gal · $${x.total_fuel_cost_usd} fuel · estimate $${x.estimated_trip_fuel_cost_usd}<br>Timings ${JSON.stringify(b.meta.timings)}<br>${Object.values(b.assumptions).join(' · ')}`;map.eachLayer(l=>{if(l instanceof L.Polyline||l instanceof L.Marker)map.removeLayer(l)});if(b.route.geometry){const line=L.geoJSON(b.route.geometry).addTo(map);map.fitBounds(line.getBounds())}L.marker([b.start.lat,b.start.lng],{icon:L.divIcon({className:'',html:'🟢'})}).addTo(map);b.fuel_stops.forEach((st,i)=>L.marker([st.lat,st.lng],{icon:L.divIcon({className:'',html:'🟠'+(i+1)})}).bindPopup(`${st.name}<br>${st.city}, ${st.state}<br>$${st.price_per_gallon_usd}/gal · ${st.gallons_purchased} gal · $${st.cost_usd}<br>Mile ${st.mile_marker}`).addTo(map));L.marker([b.finish.lat,b.finish.lng],{icon:L.divIcon({className:'',html:'🔴'})}).addTo(map)}document.querySelector('form').onsubmit=e=>{e.preventDefault();load()};load();</script></body></html>'''

