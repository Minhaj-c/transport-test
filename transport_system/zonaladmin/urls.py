from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path("", views.zonal_dashboard, name="zonal-dashboard"),

    # Pre-informs
    path("preinforms/", views.zonal_preinforms, name="zonal-preinforms"),
    path("preinforms/noted/<int:preinform_id>/", views.mark_preinform_noted, name="mark-preinform-noted"),
    path("preinforms/cancel/<int:preinform_id>/", views.cancel_preinform, name="cancel-preinform"),

    #routes
    path("routes/", views.zonal_routes, name="zonal-routes"),

    # Schedules
    path("schedules/", views.zonal_schedules, name="zonal-schedules"),
    path("schedules/load/<int:schedule_id>/", views.schedule_load_prediction, name="schedule-load-prediction"),

    # Assign bus
    path("assign-bus/", views.assign_bus_view, name="assign-bus"),

    # Demand alerts
    path("demand/", views.zonal_demand_alerts, name="zonal-demand"),

    # Spare bus action (added in phase 2)
    path("demand/dispatch/<int:alert_id>/", views.dispatch_spare_bus, name="zonal-dispatch-spare"),
]
