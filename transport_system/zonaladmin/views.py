from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.exceptions import FieldDoesNotExist
from users.models import CustomUser

from preinforms.models import PreInform
from schedules.models import Schedule, Bus
from routes.models import Route
from demand.models import DemandAlert


# Helper: get zone-specific queryset
def filter_zone(queryset, user):
    """
    Return zone-filtered queryset for zonal admins, full for superusers/admin.
    Works for:
      - Route (has `zone`)
      - Models with `route` FK (PreInform, Schedule, etc.)
      - Models with `stop` FK (DemandAlert -> stop -> route -> zone)
    """
    # Superuser & central admin: see everything
    if user.is_superuser or getattr(user, "role", None) == "admin":
        return queryset

    # Zonal admin: filter by their zone
    if getattr(user, "role", None) == "zonal_admin" and getattr(user, "zone_id", None):
        model = queryset.model
        opts = model._meta

        # Case 1: model has direct `zone` field (Route)
        try:
            opts.get_field("zone")
            return queryset.filter(zone=user.zone)
        except FieldDoesNotExist:
            pass

        # Case 2: model has `route` FK with zone (PreInform, Schedule)
        try:
            opts.get_field("route")
            return queryset.filter(route__zone=user.zone)
        except FieldDoesNotExist:
            pass

        # Case 3: model has `stop` FK (DemandAlert -> stop -> route -> zone)
        try:
            opts.get_field("stop")
            return queryset.filter(stop__route__zone=user.zone)
        except FieldDoesNotExist:
            pass

        # If we don't know how to filter this model by zone
        return queryset.none()

    # Everyone else (drivers, passengers) -> no access to zonal data by default
    return queryset.none()


# --------------------------
# 1) ZONAL DASHBOARD
# --------------------------
@login_required
def zonal_dashboard(request):
    user = request.user

    # Pre-informs in this zone
    preinforms = filter_zone(PreInform.objects.all(), user)[:5]

    # Today's schedules in this zone
    today = timezone.localdate()
    schedules = filter_zone(
        Schedule.objects.filter(date=today),
        user
    )[:5]

    # Demand alerts in this zone
    demands = filter_zone(DemandAlert.objects.all(), user)[:5]

    # Routes in this zone
    routes = filter_zone(Route.objects.all(), user)[:5]

    context = {
        "user": user,
        "preinforms": preinforms,
        "schedules": schedules,
        "demands": demands,
        "routes": routes,
    }

    return render(request, "zonaladmin/dashboard.html", context)


# --------------------------
# 2) PREINFORM LIST PAGE
# --------------------------
@login_required
def zonal_preinforms(request):
    user = request.user
    preinforms = filter_zone(PreInform.objects.all(), user)
    return render(request, "zonaladmin/preinforms.html", {"preinforms": preinforms})


# --------------------------
# 3) CANCEL PREINFORM ACTION
# --------------------------
@login_required
def cancel_preinform(request, preinform_id):
    user = request.user

    # Only admin or zonal_admin should be allowed here
    if not (user.is_superuser or user.role in ["admin", "zonal_admin"]):
        return redirect("zonal-preinforms")

    preinform = get_object_or_404(PreInform, id=preinform_id)

    # Zonal admin: ensure it belongs to their zone
    if user.role == "zonal_admin" and preinform.route.zone != user.zone:
        return redirect("zonal-preinforms")

    preinform.status = "cancelled"
    preinform.save()
    return redirect("zonal-preinforms")


# --------------------------
# 4) SCHEDULES PAGE (list)
# --------------------------
@login_required
def zonal_schedules(request):
    user = request.user
    schedules = filter_zone(Schedule.objects.all(), user)
    return render(request, "zonaladmin/schedules.html", {"schedules": schedules})


# --------------------------
# 5) ASSIGN BUS PAGE
# --------------------------
from users.models import CustomUser

@login_required
def assign_bus_view(request):
    user = request.user

    # Only routes in this zonal admin's zone
    routes = filter_zone(Route.objects.all(), user)

    # All buses (you can later filter by zone if needed)
    buses = Bus.objects.all()

    # Drivers (filter by zone for zonal admins)
    if user.role == "zonal_admin":
        drivers = CustomUser.objects.filter(role="driver", zone=user.zone)
    else:
        drivers = CustomUser.objects.filter(role="driver")

    if request.method == "POST":
        route_id = request.POST.get("route")
        bus_id = request.POST.get("bus")
        driver_id = request.POST.get("driver")
        date = request.POST.get("date")
        departure = request.POST.get("departure_time")
        arrival = request.POST.get("arrival_time")

        # Validate route
        route = get_object_or_404(Route, id=route_id)

        # Zonal admin only allowed to assign routes in their zone
        if user.role == "zonal_admin" and route.zone != user.zone:
            return redirect("zonal-schedules")

        # Get bus & driver objects
        bus = get_object_or_404(Bus, id=bus_id)
        driver = get_object_or_404(CustomUser, id=driver_id, role="driver")

        # IMPORTANT: auto-fill seats from bus.capacity
        Schedule.objects.create(
            route=route,
            bus=bus,
            driver=driver,
            date=date,
            departure_time=departure,
            arrival_time=arrival,
            total_seats=bus.capacity,
            available_seats=bus.capacity,
        )

        return redirect("zonal-schedules")

    return render(request, "zonaladmin/assign_bus.html", {
        "routes": routes,
        "buses": buses,
        "drivers": drivers,
    })


# --------------------------
# 6) DEMAND ALERT PAGE
# --------------------------
@login_required
def zonal_demand_alerts(request):
    user = request.user
    alerts = filter_zone(DemandAlert.objects.all(), user)
    return render(request, "zonaladmin/demand.html", {"alerts": alerts})


# --------------------------
# 7) ROUTES PAGE
# --------------------------
@login_required
def zonal_routes(request):
    user = request.user
    routes = filter_zone(Route.objects.all(), user)
    return render(request, "zonaladmin/routes.html", {"routes": routes})
