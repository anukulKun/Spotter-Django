"""HTTP views for the fuel-route API and small presentation pages."""

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from routing.models import ImportRun
from routing.optimizer import InfeasibleRoute
from routing.providers.base import NoRouteError, RoutingProviderError, RoutingTimeout
from routing.providers.geocode import LocationError, LocationNotInUs
from routing.services.planner import Planner
from routing.station_index import stations


def error(code: str, message: str, http_status: int, details: dict | None = None) -> Response:
    """Build the API's JSON error envelope."""
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return Response(body, status=http_status)


class RouteView(APIView):
    """Plan a route from either query parameters or a JSON POST body."""

    planner_factory = staticmethod(Planner)
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """Handle a GET route request."""
        return self.handle(dict(request.query_params))

    def post(self, request):
        """Handle a JSON route request."""
        return self.handle(request.data)

    def handle(self, data):
        """Validate the request and translate domain errors into JSON."""
        start = data.get("start")
        finish = data.get("finish")
        if isinstance(start, list):
            start = start[0]
        if isinstance(finish, list):
            finish = finish[0]
        if not start or not finish:
            return error(
                "INVALID_PARAMS", "start and finish are required", status.HTTP_400_BAD_REQUEST
            )
        params = {}
        for key in (
            "range_miles",
            "mpg",
            "starting_fuel_gallons",
            "corridor_miles",
            "stop_penalty_usd",
            "geometry",
        ):
            value = data.get(key)
            params[key] = value[0] if isinstance(value, list) else value
            if value is None:
                params.pop(key, None)
        try:
            return Response(self.planner_factory().plan(start, finish, params))
        except LocationNotInUs as exc:
            return error(exc.code, str(exc), status.HTTP_400_BAD_REQUEST)
        except LocationError as exc:
            return error(exc.code, str(exc), status.HTTP_400_BAD_REQUEST)
        except ValueError as exc:
            return error("INVALID_PARAMS", str(exc), status.HTTP_400_BAD_REQUEST)
        except InfeasibleRoute as exc:
            minimum = int(exc.min_range_miles_needed)
            details = {
                "gap_start_mile": exc.gap_start_mile,
                "gap_end_mile": exc.gap_end_mile,
                "range_miles": exc.range_miles,
                "min_range_miles_needed": minimum,
                "suggestion": (
                    f"Increase range_miles to at least {minimum}, or pick a route with more stations; "
                    "this dataset has sparse station coverage on this corridor."
                ),
            }
            return error(
                "NO_FUEL_STATION_IN_RANGE", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY, details
            )
        except LookupError as exc:
            return error("FUEL_DATA_NOT_LOADED", str(exc), status.HTTP_503_SERVICE_UNAVAILABLE)
        except NoRouteError as exc:
            return error("NO_ROUTE", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY)
        except RoutingTimeout as exc:
            return error("ROUTING_PROVIDER_TIMEOUT", str(exc), status.HTTP_504_GATEWAY_TIMEOUT)
        except RoutingProviderError as exc:
            return error("ROUTING_PROVIDER_ERROR", str(exc), status.HTTP_502_BAD_GATEWAY)
        except Exception as exc:
            return error("ROUTING_PROVIDER_ERROR", str(exc), status.HTTP_502_BAD_GATEWAY)


class HealthView(APIView):
    """Report whether station data is loaded."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """Return the station-data health status."""
        count = len(stations())
        if not count:
            return error(
                "FUEL_DATA_NOT_LOADED",
                "Fuel data has not been imported",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        version = (
            ImportRun.objects.order_by("-created_at").values_list("data_version", flat=True).first()
            or "empty"
        )
        return Response({"status": "ok", "stations_loaded": count, "data_version": version})


def home(request):
    """Render the minimal landing page."""
    return HttpResponse(
        "<!doctype html><html><head><title>Fuel Route Planner</title></head><body>"
        "<h1>Fuel Route Planner</h1><p>Plan a US trip with fuel stops, costs, and a route map.</p>"
        '<ul><li><a href="/map/?start=Dallas%2C%20TX&amp;finish=Chicago%2C%20IL">Dallas to Chicago</a></li>'
        '<li><a href="/map/?start=New%20York%2C%20NY&amp;finish=Miami%2C%20FL">New York to Miami</a></li>'
        '<li><a href="/map/?start=Denver%2C%20CO&amp;finish=Kansas%20City%2C%20MO">Denver to Kansas City</a></li></ul>'
        "</body></html>"
    )


def map_view(request):
    """Render the plain HTML map page."""
    return render(request, "routing/map.html")


def map_js(request):
    """Serve the map page's static JavaScript without requiring collectstatic."""
    path = settings.BASE_DIR / "routing" / "static" / "routing" / "map.js"
    return HttpResponse(path.read_text(encoding="utf-8"), content_type="application/javascript")


def favicon(request):
    """Return an empty favicon response."""
    return HttpResponse(status=204)
