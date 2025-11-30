from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Sum, Count

from users.models import CustomUser
from preinforms.models import PreInform
from schedules.models import Schedule, Bus
from routes.models import Route
from demand.models import DemandAlert

# Alert engines
from zonaladmin.logic.alert_engine import (
    generate_demand_alerts,
    generate_prediction_alerts,
)


# --------------------------
# Helper: zone filter
# --------------------------
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
    today = timezone.localdate()

    # If zonal admin, pass their zone to the engines
    zone = None
    if getattr(user, "role", None) == "zonal_admin" and getattr(user, "zone_id", None):
        zone = user.zone

    # Refresh today's alerts:
    #  - Pre-inform based
    #  - Prediction (live bus) based
    generate_demand_alerts(for_date=today, zone=zone)
    generate_prediction_alerts(for_date=today, zone=zone)

    # Pre-informs in this zone (recent 5 for today)
    preinforms = filter_zone(
        PreInform.objects.select_related("route", "boarding_stop", "user")
        .filter(date_of_travel=today)
        .order_by("-created_at"),
        user,
    )[:5]

    # Today's schedules in this zone
    schedules = filter_zone(
        Schedule.objects.filter(date=today).select_related("route", "bus", "driver"),
        user,
    )[:5]

    # Demand alerts in this zone (today only)
    demands_qs = filter_zone(
        DemandAlert.objects.select_related("stop", "stop__route", "user"),
        user,
    ).filter(created_at__date=today).order_by("-created_at")
    demands = list(demands_qs[:5])

    # Simple summary counts by intensity (based on people count)
    high_critical_count = demands_qs.filter(number_of_people__gte=40).count()
    medium_count = demands_qs.filter(
        number_of_people__gte=20, number_of_people__lt=40
    ).count()

    # Routes in this zone
    routes = filter_zone(Route.objects.all(), user)[:5]

    context = {
        "user": user,
        "preinforms": preinforms,
        "schedules": schedules,
        "demands": demands,
        "routes": routes,
        "today": today,
        "high_critical_count": high_critical_count,
        "medium_count": medium_count,
    }

    return render(request, "zonaladmin/dashboard.html", context)


# --------------------------
# 2) PREINFORM ANALYTICS PAGE
# --------------------------
@login_required
def zonal_preinforms(request):
    """
    Mixed Option B + C:
    - Date filter
    - KPI summary cards
    - Grouped stats by Route and by Stop+Time
    - Detailed pre-inform table with Noted + Cancel options
    """
    user = request.user

    # ----- Date filter (default = today) -----
    date_str = request.GET.get("date")
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            selected_date = timezone.localdate()
    else:
        selected_date = timezone.localdate()

    # Base queryset: zone-filtered + selected date
    base_qs = filter_zone(
        PreInform.objects.filter(date_of_travel=selected_date),
        user,
    ).select_related("route", "boarding_stop", "user")

    # Full list for table
    preinforms = base_qs.order_by("desired_time")

    # ----- Summary KPIs -----
    summary = base_qs.aggregate(
        total_preinforms=Count("id"),
        total_passengers=Sum("passenger_count"),
    )
    summary["total_preinforms"] = summary["total_preinforms"] or 0
    summary["total_passengers"] = summary["total_passengers"] or 0
    summary["unique_routes"] = base_qs.values("route_id").distinct().count()
    summary["unique_stops"] = base_qs.values("boarding_stop_id").distinct().count()

    # ----- Grouped by route -----
    route_stats = base_qs.values(
        "route__id",
        "route__number",
        "route__name",
    ).annotate(
        total_passengers=Sum("passenger_count"),
        total_preinforms=Count("id"),
    ).order_by("-total_passengers")

    # ----- Grouped by stop + time -----
    stop_time_stats = base_qs.values(
        "boarding_stop__id",
        "boarding_stop__name",
        "desired_time",
    ).annotate(
        total_passengers=Sum("passenger_count"),
        total_preinforms=Count("id"),
    ).order_by("boarding_stop__name", "desired_time")

    context = {
        "user": user,
        "selected_date": selected_date,
        "summary": summary,
        "route_stats": route_stats,
        "stop_time_stats": stop_time_stats,
        "preinforms": preinforms,
    }

    return render(request, "zonaladmin/preinforms.html", context)


# --------------------------
# 2.1) MARK PREINFORM AS NOTED
# --------------------------
@login_required
def mark_preinform_noted(request, preinform_id):
    """
    Zonal admin / central admin marks a PreInform as 'noted'.
    This is still NOT a booking; just 'we saw this demand'.
    Also triggers demand alert generation for that zone + date.
    """
    user = request.user

    # Only allow POST to change status
    if request.method != "POST":
        return redirect("zonal-preinforms")

    # Only admin or zonal_admin should be allowed here
    if not (user.is_superuser or getattr(user, "role", None) in ["admin", "zonal_admin"]):
        return redirect("zonal-preinforms")

    preinform = get_object_or_404(PreInform, id=preinform_id)

    # Zonal admin: ensure it belongs to their zone
    if getattr(user, "role", None) == "zonal_admin" and preinform.route.zone != user.zone:
        return redirect("zonal-preinforms")

    # Only move pending -> noted, or keep noted as noted
    if preinform.status in ["pending", "noted"]:
        preinform.status = "noted"
        preinform.save()

        # Generate / update demand alerts from NOTED pre-informs for this zone+date
        if getattr(user, "zone_id", None):
            generate_demand_alerts(zone=user.zone, for_date=preinform.date_of_travel)

    return redirect("zonal-preinforms")


# --------------------------
# 3) CANCEL PREINFORM ACTION
# --------------------------
@login_required
def cancel_preinform(request, preinform_id):
    """
    Zonal admin / central admin can cancel a pre-inform.
    This is internal – it's NOT a booking cancellation,
    it's just marking that this pre-inform is no longer valid.
    """
    user = request.user

    # Only admin or zonal_admin should be allowed here
    if not (user.is_superuser or getattr(user, "role", None) in ["admin", "zonal_admin"]):
        return redirect("zonal-preinforms")

    preinform = get_object_or_404(PreInform, id=preinform_id)

    # Zonal admin: ensure it belongs to their zone
    if getattr(user, "role", None) == "zonal_admin" and preinform.route.zone != user.zone:
        return redirect("zonal-preinforms")

    if request.method == "POST":
        # Only cancel if not already completed/cancelled
        if preinform.status in ["pending", "noted"]:
            preinform.status = "cancelled"
            preinform.save()
        return redirect("zonal-preinforms")

    # If GET by mistake, just redirect back
    return redirect("zonal-preinforms")


# --------------------------
# 4) SCHEDULES PAGE (list)
# --------------------------
@login_required
def zonal_schedules(request):
    user = request.user
    schedules = filter_zone(
        Schedule.objects.select_related("route", "bus", "driver"),
        user,
    ).order_by("date", "departure_time")

    return render(request, "zonaladmin/schedules.html", {"schedules": schedules})


# --------------------------
# 5) ASSIGN BUS PAGE
# --------------------------
@login_required
def assign_bus_view(request):
    user = request.user

    # Only routes in this zonal admin's zone
    routes = filter_zone(Route.objects.all(), user)

    # All buses (later you can filter by zone if needed)
    buses = Bus.objects.all()

    # Drivers (filter by zone for zonal admins)
    if getattr(user, "role", None) == "zonal_admin" and getattr(user, "zone_id", None):
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
        if getattr(user, "role", None) == "zonal_admin" and route.zone != user.zone:
            return redirect("zonal-schedules")

        bus = get_object_or_404(Bus, id=bus_id)
        driver = get_object_or_404(CustomUser, id=driver_id, role="driver")

        # Auto-fill seats from bus.capacity
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

    return render(
        request,
        "zonaladmin/assign_bus.html",
        {
            "routes": routes,
            "buses": buses,
            "drivers": drivers,
        },
    )


# --------------------------
# 6) DEMAND ALERT PAGE
# --------------------------
@login_required
def zonal_demand_alerts(request):
    """
    Shows two sections:

    - Pre-inform alerts: people waiting at stops (from NOTED pre-informs)
    - Prediction alerts: expected people inside buses after each stop
      (built from running-bus prediction engine)

    For prediction alerts we try to attach a schedule_guess:
    - We don't have a schedule FK on DemandAlert
    - So we try to find a running schedule on that route & date
      and expose it as alert.derived_schedule for the template.
    """
    user = request.user

    # --- Date filter (optional, default = today) ---
    date_str = request.GET.get("date")
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            selected_date = timezone.localdate()
    else:
        selected_date = timezone.localdate()

    # Determine zone (for zonal admins only)
    zone = None
    if getattr(user, "role", None) == "zonal_admin" and getattr(user, "zone_id", None):
        zone = user.zone

    # 1) Classical demand from NOTED pre-informs
    generate_demand_alerts(for_date=selected_date, zone=zone)

    # 2) Prediction-based alerts using running buses + preinforms
    generate_prediction_alerts(for_date=selected_date, zone=zone)

    # 3) Load alerts only for this date (+ zone via filter_zone)
    base_qs = (
        DemandAlert.objects
        .select_related("stop", "stop__route", "user")   # ✅ NO 'schedule' HERE
        .filter(created_at__date=selected_date)
        .order_by("-created_at")
    )
    base_qs = filter_zone(base_qs, user)

    # Split into two groups using text we set in admin_notes
    preinform_qs = base_qs.filter(admin_notes__icontains="Pre-Informs")
    prediction_qs = base_qs.filter(admin_notes__icontains="Prediction (Bus load)")

    # Turn into lists so we can attach attributes
    preinform_alerts = list(preinform_qs)
    prediction_alerts = list(prediction_qs)

    # Try to attach a guessed schedule for prediction alerts
    for alert in prediction_alerts:
        stop_route = getattr(alert.stop, "route", None)
        if not stop_route:
            alert.derived_schedule = None
            continue

        sched = (
            Schedule.objects
            .select_related("bus")
            .filter(
                route=stop_route,
                date=selected_date,
                bus__is_running=True,
            )
            .order_by("departure_time")
            .first()
        )
        alert.derived_schedule = sched

    context = {
        "user": user,
        "selected_date": selected_date,
        "preinform_alerts": preinform_alerts,
        "prediction_alerts": prediction_alerts,
    }

    return render(request, "zonaladmin/demand.html", context)


# --------------------------
# 7) ROUTES PAGE
# --------------------------
@login_required
def zonal_routes(request):
    user = request.user
    routes = filter_zone(
        Route.objects.all().select_related("zone"),
        user,
    ).order_by("number")

    return render(request, "zonaladmin/routes.html", {"routes": routes})


# --------------------------
# 8) SCHEDULE LOAD PREDICTION PAGE
# --------------------------
@login_required
def schedule_load_prediction(request, schedule_id):
    """
    Show bus load prediction for a single schedule:
    - combines current_passengers (driver app)
    - with NOTED pre-informs for that route+date
    - shows where bus will exceed capacity
    """
    user = request.user

    # Load schedule with related route, bus, driver
    schedule = get_object_or_404(
        Schedule.objects.select_related("route", "bus", "driver"),
        id=schedule_id,
    )

    # Zonal admin: make sure this route belongs to their zone
    if getattr(user, "role", None) == "zonal_admin":
        if schedule.route.zone_id != getattr(user, "zone_id", None):
            return redirect("zonal-schedules")

    # Use our prediction logic from alert_engine
    from zonaladmin.logic.alert_engine import compute_bus_load_for_schedule

    try:
        data = compute_bus_load_for_schedule(schedule)
    except Exception as exc:
        # If anything goes wrong, show friendly error
        return render(
            request,
            "zonaladmin/schedule_load.html",
            {
                "schedule": schedule,
                "error": f"Could not compute prediction: {exc}",
            },
        )

    context = {
        "schedule": schedule,
        "data": data,
    }

    return render(request, "zonaladmin/schedule_load.html", context)
