from django.urls import path
from . import views

urlpatterns = [
    path('', views.zonal_dashboard, name='zonal-dashboard'),

    # Preinforms
    path('preinforms/', views.zonal_preinforms, name='zonal-preinforms'),
    path('preinforms/cancel/<int:preinform_id>/', views.cancel_preinform, name='cancel-preinform'),

    # Schedules
    path('schedules/', views.zonal_schedules, name='zonal-schedules'),

    # Assign Bus
    path('assign-bus/', views.assign_bus_view, name='assign-bus'),

    # Demand alerts
    path('demand/', views.zonal_demand_alerts, name='zonal-demand'),

    # Routes list
    path('routes/', views.zonal_routes, name='zonal-routes'),
]
