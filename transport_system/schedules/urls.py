"""
Schedules URL Configuration
"""

from django.urls import path
from . import views

urlpatterns = [
    # Web pages
    path('schedules/', views.schedules_page, name='schedules-page'),
    
    # API endpoints
    path('api/schedules/', views.ScheduleListView.as_view(), name='schedule-list'),
    path('api/schedules/driver/', views.driver_schedules_view, name='driver-schedules'),
    path('api/buses/nearby/', views.nearby_buses, name='nearby-buses'),
    path('api/buses/update-location/', views.update_bus_location, name='update-bus-location'),
    path('api/buses/<int:bus_id>/', views.bus_details, name='bus-details'),
    path('api/schedules/passenger-count/', views.update_passenger_count, name='update-passenger-count'),
    path( 'api/schedules/current-stop/',views.update_current_stop,name='update-current-stop'),
    
]