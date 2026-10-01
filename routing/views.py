from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
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
    return HttpResponse('<!doctype html><html><head><title>Fuel Route Planner</title></head><body><h1>Fuel Route Planner</h1><p>Plan a US trip with fuel stops, costs, and a route map.</p><ul><li><a href="/map/?start=Dallas%2C%20TX&amp;finish=Chicago%2C%20IL">Dallas to Chicago</a></li><li><a href="/map/?start=New%20York%2C%20NY&amp;finish=Miami%2C%20FL">New York to Miami</a></li><li><a href="/map/?start=Denver%2C%20CO&amp;finish=Kansas%20City%2C%20MO">Denver to Kansas City</a></li></ul></body></html>')
def map_view(request):
    return render(request, 'routing/map.html')

def map_js(request):
    path = settings.BASE_DIR / 'routing' / 'static' / 'routing' / 'map.js'
    return HttpResponse(path.read_text(encoding='utf-8'), content_type='application/javascript')

def favicon(request):
    return HttpResponse(status=204)