from django.urls import path
from .views import RouteView,HealthView,placeholder,map_view
urlpatterns=[path('',placeholder),path('map/',map_view),path('api/route/',RouteView.as_view()),path('api/health/',HealthView.as_view())]
