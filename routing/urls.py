"""URL routes for the fuel-route project."""

from django.urls import path

from .views import HealthView, RouteView, favicon, home, map_js, map_view

urlpatterns = [
    path("", home),
    path("map/", map_view),
    path("api/route/", RouteView.as_view()),
    path("api/route", RouteView.as_view()),
    path("api/health/", HealthView.as_view()),
    path("static/routing/map.js", map_js),
    path("favicon.ico", favicon),
]
