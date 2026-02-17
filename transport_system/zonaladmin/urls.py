from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path("", views.zonal_dashboard, name="zonal-dashboard"),

    # Pre-informs
    path("preinforms/", views.zonal_preinforms, name="zonal-preinforms"),
    path("preinforms/noted/<int:preinform_id>/", views.mark_preinform_noted, name="mark-preinform-noted"),
    path("preinforms/cancel/<int:preinform_id>/", views.cancel_preinform, name="cancel-preinform"),

    # 🔥 BUS MANAGEMENT
    path("buses/", views.zonal_buses, name="zonal-buses"),
    path("buses/add/", views.add_bus, name="add-bus"),
    path("buses/edit/<int:bus_id>/", views.edit_bus, name="edit-bus"),

    # 🔥 ROUTE MANAGEMENT
    path("routes/", views.manage_routes, name="manage-routes"),
    path("routes/add/", views.add_route, name="add-route"),
    path("routes/edit/<int:route_id>/", views.edit_route, name="edit-route"),

    # Schedules
    path("schedules/", views.zonal_schedules, name="zonal-schedules"),
    path("schedules/load/<int:schedule_id>/", views.schedule_load_prediction, name="schedule-load-prediction"),
    path('schedules/<int:schedule_id>/verify/', views.verify_schedule_view, name='verify-schedule'),

    # Assign bus
    path("assign-bus/", views.assign_bus_view, name="assign-bus"),

    # Demand alerts
    path("demand/", views.zonal_demand_alerts, name="zonal-demand"),
    path("demand/dispatch/<int:alert_id>/", views.dispatch_spare_bus, name="zonal-dispatch-spare"),
    
    path("stops/", views.all_routes_for_stops, name="all-routes-for-stops"),
    path("routes/<int:route_id>/stops/", views.manage_stops, name="manage-stops"),
    path("routes/<int:route_id>/stops/add/", views.add_stop, name="add-stop"),
    path("routes/<int:route_id>/stops/<int:stop_id>/edit/", views.edit_stop, name="edit-stop"),
    path("routes/<int:route_id>/stops/<int:stop_id>/delete/", views.delete_stop, name="delete-stop"),
    
    path("weekly-profit/", views.weekly_profit_dashboard, name="weekly-profit"),
    
    path('schedule-generator/', views.schedule_generator, name='schedule-generator'),
    path('generate-week-schedules/', views.generate_week_schedules, name='generate-week-schedules'),
    path('calculate-week-profits/', views.calculate_week_profits, name='calculate-week-profits'),
]