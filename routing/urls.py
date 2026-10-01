from django.urls import path
from .views import RouteView,HealthView,placeholder,map_view,map_js,favicon
urlpatterns=[path('',placeholder),path('map/',map_view),path('api/route/',RouteView.as_view()),path('api/health/',HealthView.as_view()),path('static/routing/map.js',map_js),path('favicon.ico',favicon)]
