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
    path('api/schedules/<int:schedule_id>/forecast/',views.schedule_forecast_view,name='schedule-forecast'),
    path('api/schedules/spare/enter/', views.enter_spare_mode, name='spare-enter'),
    path('api/schedules/spare/status/', views.get_spare_status, name='spare-status'),
    path('api/schedules/spare/request/', views.request_spare_bus, name='spare-request'),
    path('api/schedules/spare/delayed/', views.report_delayed_arrival, name='spare-delayed'),
    path('api/schedules/spare/exit/', views.exit_spare_mode, name='spare-exit'),
    path('api/schedules/spare/complete/', views.complete_spare_trip, name='spare-complete'),
    path('api/schedules/issue-ticket/', views.issue_ticket, name='issue-ticket'),
    path('api/schedules/arrived-at-stop/', views.arrived_at_stop, name='arrived-at-stop'),   
    
]