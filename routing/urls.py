from django.urls import path
from .views import RouteView,HealthView,placeholder
urlpatterns=[path('',placeholder),path('api/route/',RouteView.as_view()),path('api/health/',HealthView.as_view())]
