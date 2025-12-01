"""
Routes URL Configuration
"""

from django.urls import path
from . import views

urlpatterns = [
    # Web pages
    path('', views.homepage, name='homepage'),
    
    # API endpoints
    path('api/routes/', views.RouteListView.as_view(), name='route-list'),
    path('api/routes/<int:pk>/', views.RouteDetailView.as_view(), name='route-detail'),
    path('api/routes/<int:route_id>/stops/', views.route_stops_view, name='route-stops'),
    path("api/routes/<int:route_id>/live-status/",views.route_live_status_view,name="route-live-status",
),

]