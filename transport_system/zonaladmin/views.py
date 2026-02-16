from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Sum, Count

from users.models import CustomUser
from preinforms.models import PreInform
from schedules.models import Schedule, Bus
from routes.models import Route, Stop
from demand.models import DemandAlert
from django.contrib import messages

# Alert engines – ONLY these (❌ no build_prediction_alerts_for_ui)
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
    route_stats = (
        base_qs.values(
            "route__id",
            "route__number",
            "route__name",
        )
        .annotate(
            total_passengers=Sum("passenger_count"),
            total_preinforms=Count("id"),
        )
        .order_by("-total_passengers")
    )

    # ----- Grouped by stop + time -----
    stop_time_stats = (
        base_qs.values(
            "boarding_stop__id",
            "boarding_stop__name",
            "desired_time",
        )
        .annotate(
            total_passengers=Sum("passenger_count"),
            total_preinforms=Count("id"),
        )
        .order_by("boarding_stop__name", "desired_time")
    )

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
    Demand alerts page with schedule lookup for prediction alerts
    """
    user = request.user

    # Date filter
    date_str = request.GET.get("date")
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            selected_date = timezone.localdate()
    else:
        selected_date = timezone.localdate()

    # Zone filter
    zone = None
    if getattr(user, "role", None) == "zonal_admin" and getattr(user, "zone_id", None):
        zone = user.zone

    # Generate alerts
    generate_demand_alerts(for_date=selected_date, zone=zone)
    generate_prediction_alerts(for_date=selected_date, zone=zone)

    # Load alerts
    base_qs = (
        DemandAlert.objects.select_related("stop", "stop__route", "user")
        .filter(created_at__date=selected_date)
        .order_by("stop__route__number", "stop__sequence", "-created_at")
    )

    base_qs = filter_zone(base_qs, user)

    # Split alerts
    preinform_alerts = base_qs.filter(admin_notes__icontains="Pre-Informs")
    prediction_alerts = base_qs.filter(admin_notes__icontains="Prediction (Bus load)")

    # 🔥 NEW: Find the schedule for each prediction alert
    prediction_alerts_with_schedule = []
    for alert in prediction_alerts:
        # Find running schedule on this route for this date
        schedule = Schedule.objects.filter(
            route=alert.stop.route,
            date=selected_date,
            bus__is_running=True
        ).select_related('bus', 'driver').first()

        prediction_alerts_with_schedule.append({
            'alert': alert,
            'bus_schedule': schedule,
            'level': alert.get_level()
        })

    context = {
        "user": user,
        "selected_date": selected_date,
        "preinform_alerts": preinform_alerts,
        "prediction_alerts": prediction_alerts,  # Keep for count
        "prediction_alerts_with_schedule": prediction_alerts_with_schedule,  # NEW
    }

    return render(request, "zonaladmin/demand.html", context)


# --------------------------
# 6b) DISPATCH SPARE BUS FROM ALERT
# --------------------------
@login_required
def dispatch_spare_bus(request, alert_id):
    """
    Zonal / central admin uses this page to convert an alert into
    a real spare-bus schedule that starts from the overflow stop.

    - Takes a DemandAlert (usually prediction-based).
    - Identifies the overflow stop from the alert.
    - Lets admin pick:
        * Spare bus (from idle, active buses)
        * Driver
        * Date & departure time
    - Creates a new Schedule with starting_stop_sequence set to overflow stop.
    - Marks bus as running and links it to that schedule.
    - Marks alert as 'dispatched' + updates admin_notes.
    """
    user = request.user

    alert = get_object_or_404(
        DemandAlert.objects.select_related("stop", "stop__route"),
        id=alert_id,
    )

    # Zonal admin: restrict to own zone
    if getattr(user, "role", None) == "zonal_admin" and getattr(user, "zone_id", None):
        if alert.stop.route.zone_id != user.zone_id:
            return redirect("zonal-demand")

    route = alert.stop.route
    overflow_stop = alert.stop  # 🔥 This is where the overflow occurs
    
    # Default date: alert creation date (or today fallback)
    alert_date = getattr(alert, "created_at", None)
    if alert_date is not None:
        selected_date = alert_date.date()
    else:
        selected_date = timezone.localdate()

    # Candidate spare buses: active & currently not running
    buses = Bus.objects.filter(is_active=True, is_running=False).order_by("number_plate")

    # Drivers (filter by zone if zonal admin)
    if getattr(user, "role", None) == "zonal_admin" and getattr(user, "zone_id", None):
        drivers = CustomUser.objects.filter(role="driver", zone=user.zone)
    else:
        drivers = CustomUser.objects.filter(role="driver")

    # Remaining stops from overflow point
    remaining_stops = route.stops.filter(
        sequence__gte=overflow_stop.sequence
    ).order_by('sequence')

    error = None

    if request.method == "POST":
        bus_id = request.POST.get("bus_id")
        driver_id = request.POST.get("driver_id")
        date_str = request.POST.get("date")
        departure_time_str = request.POST.get("departure_time")
        arrival_time_str = request.POST.get("arrival_time")

        # Parse date
        try:
            sched_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            sched_date = selected_date

        # Parse times (HH:MM)
        try:
            departure_time = datetime.strptime(departure_time_str, "%H:%M").time()
        except Exception:
            departure_time = None

        try:
            arrival_time = (
                datetime.strptime(arrival_time_str, "%H:%M").time()
                if arrival_time_str
                else None
            )
        except Exception:
            arrival_time = None

        if not (bus_id and driver_id and departure_time):
            error = "Please select a spare bus, driver and departure time."
        else:
            bus_obj = get_object_or_404(Bus, id=bus_id)
            driver_obj = get_object_or_404(CustomUser, id=driver_id, role="driver")

            # 🔥 CHECK IF SCHEDULE ALREADY EXISTS
            existing_schedule = Schedule.objects.filter(
                bus=bus_obj,
                date=sched_date,
                departure_time=departure_time
            ).first()

            if existing_schedule:
                error = (
                    f"Bus {bus_obj.number_plate} already has a schedule "
                    f"on {sched_date} at {departure_time}. "
                    f"Choose a different time or bus."
                )
            else:
                # 🔥 Create the spare schedule starting from overflow stop
                schedule = Schedule.objects.create(
                    route=route,
                    bus=bus_obj,
                    driver=driver_obj,
                    date=sched_date,
                    departure_time=departure_time,
                    arrival_time=arrival_time or departure_time,
                    total_seats=bus_obj.capacity,
                    available_seats=bus_obj.capacity,
                    current_stop_sequence=overflow_stop.sequence,  # Current position (will change)
                    starting_stop_sequence=overflow_stop.sequence,  # 🔥 ORIGINAL START (never changes)
                    is_spare_trip=True,
                    source_alert=alert,
                )

                # Mark bus as running on this route/schedule (NO GPS)
                bus_obj.is_running = True
                bus_obj.current_route = route
                bus_obj.current_schedule = schedule
                bus_obj.save(
                    update_fields=[
                        "is_running",
                        "current_route",
                        "current_schedule",
                    ]
                )

                # Update alert status & notes
                if hasattr(alert, "status"):
                    alert.status = "dispatched"

                extra_note = (
                    f" Spare bus {bus_obj.number_plate} dispatched "
                    f"from stop '{overflow_stop.name}' (seq: {overflow_stop.sequence}) "
                    f"(schedule #{schedule.id})."
                )
                if alert.admin_notes:
                    alert.admin_notes = alert.admin_notes + extra_note
                else:
                    alert.admin_notes = extra_note
                alert.save(
                    update_fields=["admin_notes"]
                    + (["status"] if hasattr(alert, "status") else [])
                )

                # Back to demand list
                return redirect("zonal-demand")

    # Default suggested departure time = now (HH:MM)
    initial_departure = timezone.localtime().strftime("%H:%M")

    context = {
        "user": user,
        "alert": alert,
        "route": route,
        "overflow_stop": overflow_stop,  # 🔥 Pass to template
        "remaining_stops": remaining_stops,  # 🔥 Pass to template
        "selected_date": selected_date,
        "buses": buses,
        "drivers": drivers,
        "initial_departure": initial_departure,
        "error": error,
    }

    return render(request, "zonaladmin/dispatch_spare_bus.html", context)
# --------------------------
# 7) ROUTES PAGE
# --------------------------
@login_required
def zonal_routes(request):
    """
    Simple list of routes for Zonal Admin.
    We do NOT depend on any zone field to avoid breaking models.
    """
    routes = Route.objects.all().order_by("number")

    # stop count per route
    stop_counts_qs = (
        Stop.objects.values("route_id").annotate(count=Count("id"))
    )
    stop_count_map = {row["route_id"]: row["count"] for row in stop_counts_qs}

    for r in routes:
        r.stop_count = stop_count_map.get(r.id, 0)

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

    # 🔥 Add starting_stop_sequence to context
    context = {
        "schedule": schedule,
        "data": data,
        "starting_sequence": getattr(schedule, "starting_stop_sequence", 0) or 0,  # 🔥 ORIGINAL start
        "current_sequence": getattr(schedule, "current_stop_sequence", 0) or 0,    # 🔥 Current position
    }

    return render(request, "zonaladmin/schedule_load.html", context)

# Add to zonaladmin/views.py

@login_required
def verify_schedule_view(request, schedule_id):
    """
    Detailed view to verify a schedule, especially spare buses.
    Shows starting point, route coverage, and all related info.
    Uses starting_stop_sequence (never changes) instead of current_stop_sequence (changes as bus moves).
    """
    user = request.user
    
    schedule = get_object_or_404(
        Schedule.objects.select_related("route", "bus", "driver"),
        id=schedule_id,
    )
    
    # Zonal admin: ensure it belongs to their zone
    if getattr(user, "role", None) == "zonal_admin" and getattr(user, "zone_id", None):
        if schedule.route.zone_id != user.zone_id:
            return redirect("zonal-schedules")
    
    route = schedule.route
    
    # Get all stops for this route
    all_stops = route.stops.all().order_by("sequence")
    
    # 🔥 USE starting_stop_sequence (ORIGINAL start point that never changes)
    start_seq = getattr(schedule, "starting_stop_sequence", 0) or 0
    
    # 🔥 ALSO get current position (where bus is NOW)
    current_seq = getattr(schedule, "current_stop_sequence", 0) or 0
    
    if start_seq > 0:
        # Spare bus or mid-route schedule - show stops from ORIGINAL start
        serving_stops = all_stops.filter(sequence__gte=start_seq)
        skipped_stops = all_stops.filter(sequence__lt=start_seq)
    else:
        # Regular full-route schedule
        serving_stops = all_stops
        skipped_stops = []
    
    # Get the starting stop (based on ORIGINAL start)
    starting_stop = all_stops.filter(sequence=start_seq).first() if start_seq > 0 else None
    
    # Get current stop (where bus is NOW)
    current_stop = all_stops.filter(sequence=current_seq).first() if current_seq > 0 else None
    
    context = {
        "user": user,
        "schedule": schedule,
        "route": route,
        "all_stops": all_stops,
        "serving_stops": serving_stops,
        "skipped_stops": skipped_stops,
        "starting_stop": starting_stop,  # ORIGINAL start
        "current_stop": current_stop,    # Current position
        "start_sequence": start_seq,     # 🔥 ORIGINAL starting point (never changes)
        "current_sequence": current_seq, # 🔥 Current position (changes as bus moves)
        "is_spare": getattr(schedule, "is_spare_trip", False),
        "source_alert": getattr(schedule, "source_alert", None),
    }
    
    return render(request, "zonaladmin/verify_schedule.html", context)

# Also add this helper to the schedules list page
@login_required
def zonal_schedules(request):
    """Enhanced schedules list with spare bus indicators"""
    user = request.user
    schedules = filter_zone(
        Schedule.objects.select_related("route", "bus", "driver")
        .prefetch_related("route__stops"),
        user,
    ).order_by("date", "departure_time")
    
    # Annotate each schedule with starting stop info
    for schedule in schedules:
        start_seq = getattr(schedule, "current_stop_sequence", 0) or 0
        if start_seq > 0:
            schedule.starting_stop = (
                schedule.route.stops
                .filter(sequence=start_seq)
                .first()
            )
        else:
            schedule.starting_stop = None

    return render(request, "zonaladmin/schedules.html", {"schedules": schedules})


# Add to zonaladmin/views.py

# --------------------------
# BUS MANAGEMENT
# --------------------------
@login_required
def zonal_buses(request):
    """
    List all buses. Zonal admins see all buses (can assign any to their routes).
    Central admin sees all.
    """
    user = request.user
    
    # All buses (zonal admins can assign any bus to their routes)
    buses = Bus.objects.all().order_by("number_plate")
    
    # Annotate with current assignment info
    for bus in buses:
        # Find current schedule
        current_schedule = Schedule.objects.filter(
            bus=bus,
            date=timezone.localdate(),
            bus__is_running=True
        ).select_related('route').first()
        
        bus.current_assignment = current_schedule
    
    context = {
        "user": user,
        "buses": buses,
    }
    
    return render(request, "zonaladmin/buses.html", context)


@login_required
def add_bus(request):
    """
    Add a new bus to the fleet.
    """
    user = request.user
    
    # Only admin and zonal_admin can add buses
    if not (user.is_superuser or getattr(user, "role", None) in ["admin", "zonal_admin"]):
        return redirect("zonal-buses")
    
    error = None
    
    if request.method == "POST":
        number_plate = request.POST.get("number_plate", "").strip()
        capacity = request.POST.get("capacity")
        mileage = request.POST.get("mileage")
        service_type = request.POST.get("service_type", "all_stop")
        
        if not number_plate or not capacity:
            error = "Number plate and capacity are required."
        else:
            # Check if bus already exists
            if Bus.objects.filter(number_plate=number_plate).exists():
                error = f"Bus with number plate '{number_plate}' already exists."
            else:
                try:
                    Bus.objects.create(
                        number_plate=number_plate,
                        capacity=int(capacity),
                        mileage=float(mileage) if mileage else 5.0,
                        service_type=service_type,
                        is_active=True,
                    )
                    return redirect("zonal-buses")
                except Exception as e:
                    error = f"Error creating bus: {str(e)}"
    
    context = {
        "user": user,
        "error": error,
        "service_types": Bus.SERVICE_TYPES,
    }
    
    return render(request, "zonaladmin/add_bus.html", context)


@login_required
def edit_bus(request, bus_id):
    """
    Edit existing bus details.
    """
    user = request.user
    
    # Only admin and zonal_admin can edit buses
    if not (user.is_superuser or getattr(user, "role", None) in ["admin", "zonal_admin"]):
        return redirect("zonal-buses")
    
    bus = get_object_or_404(Bus, id=bus_id)
    error = None
    
    if request.method == "POST":
        number_plate = request.POST.get("number_plate", "").strip()
        capacity = request.POST.get("capacity")
        mileage = request.POST.get("mileage")
        service_type = request.POST.get("service_type")
        is_active = request.POST.get("is_active") == "on"
        
        if not number_plate or not capacity:
            error = "Number plate and capacity are required."
        else:
            # Check if number plate is taken by another bus
            existing = Bus.objects.filter(number_plate=number_plate).exclude(id=bus_id).first()
            if existing:
                error = f"Number plate '{number_plate}' is already used by another bus."
            else:
                try:
                    bus.number_plate = number_plate
                    bus.capacity = int(capacity)
                    bus.mileage = float(mileage) if mileage else bus.mileage
                    bus.service_type = service_type
                    bus.is_active = is_active
                    bus.save()
                    return redirect("zonal-buses")
                except Exception as e:
                    error = f"Error updating bus: {str(e)}"
    
    context = {
        "user": user,
        "bus": bus,
        "error": error,
        "service_types": Bus.SERVICE_TYPES,
    }
    
    return render(request, "zonaladmin/edit_bus.html", context)


# --------------------------
# ROUTE MANAGEMENT
# --------------------------
@login_required
def manage_routes(request):
    """
    Enhanced route management page showing routes in the zone.
    """
    user = request.user
    
    # Zone-filtered routes
    routes = filter_zone(Route.objects.all(), user).order_by("number")
    
    # Annotate with stop count
    stop_counts_qs = Stop.objects.values("route_id").annotate(count=Count("id"))
    stop_count_map = {row["route_id"]: row["count"] for row in stop_counts_qs}
    
    for r in routes:
        r.stop_count = stop_count_map.get(r.id, 0)
    
    context = {
        "user": user,
        "routes": routes,
    }
    
    return render(request, "zonaladmin/manage_routes.html", context)


@login_required
def add_route(request):
    """
    Add a new route in the zonal admin's zone.
    After creation, redirects to manage stops page.
    """
    user = request.user
    
    # Only admin and zonal_admin can add routes
    if not (user.is_superuser or getattr(user, "role", None) in ["admin", "zonal_admin"]):
        messages.error(request, "Permission denied.")
        return redirect("manage-routes")
    
    error = None
    
    if request.method == "POST":
        number = request.POST.get("number", "").strip()
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        origin = request.POST.get("origin", "").strip()
        destination = request.POST.get("destination", "").strip()
        total_distance = request.POST.get("total_distance")
        duration = request.POST.get("duration")
        turnaround_time = request.POST.get("turnaround_time", "0.33")
        buffer_time = request.POST.get("buffer_time", "0.16")
        
        if not all([number, name, origin, destination, total_distance, duration]):
            error = "All required fields must be filled."
        else:
            # Check if route number already exists
            if Route.objects.filter(number=number).exists():
                error = f"Route number '{number}' already exists."
            else:
                try:
                    # Assign zone for zonal admin
                    zone = None
                    if getattr(user, "role", None) == "zonal_admin":
                        zone = user.zone
                    
                    # Create the route
                    route = Route.objects.create(
                        number=number,
                        name=name,
                        description=description,
                        origin=origin,
                        destination=destination,
                        total_distance=float(total_distance),
                        duration=float(duration),
                        turnaround_time=float(turnaround_time) if turnaround_time else 0.33,
                        buffer_time=float(buffer_time) if buffer_time else 0.16,
                        zone=zone,
                    )
                    
                    messages.success(request, f"Route {number} created successfully! Now add stops.")
                    
                    # 🔥 REDIRECT TO MANAGE STOPS PAGE
                    return redirect("manage-stops", route_id=route.id)
                    
                except Exception as e:
                    error = f"Error creating route: {str(e)}"
    
    context = {
        "user": user,
        "error": error,
    }
    
    return render(request, "zonaladmin/add_route.html", context)

@login_required
def edit_route(request, route_id):
    """
    Edit existing route.
    """
    user = request.user
    
    # Only admin and zonal_admin can edit routes
    if not (user.is_superuser or getattr(user, "role", None) in ["admin", "zonal_admin"]):
        return redirect("manage-routes")
    
    route = get_object_or_404(Route, id=route_id)
    
    # Zonal admin: ensure route belongs to their zone
    if getattr(user, "role", None) == "zonal_admin" and route.zone != user.zone:
        return redirect("manage-routes")
    
    error = None
    
    if request.method == "POST":
        number = request.POST.get("number", "").strip()
        name = request.POST.get("name", "").strip()
        origin = request.POST.get("origin", "").strip()
        destination = request.POST.get("destination", "").strip()
        total_distance = request.POST.get("total_distance")
        duration = request.POST.get("duration")
        
        if not all([number, name, origin, destination, total_distance, duration]):
            error = "All fields are required."
        else:
            # Check if route number is taken by another route
            existing = Route.objects.filter(number=number).exclude(id=route_id).first()
            if existing:
                error = f"Route number '{number}' is already used."
            else:
                try:
                    route.number = number
                    route.name = name
                    route.origin = origin
                    route.destination = destination
                    route.total_distance = float(total_distance)
                    route.duration = float(duration)
                    route.save()
                    return redirect("manage-routes")
                except Exception as e:
                    error = f"Error updating route: {str(e)}"
    
    # Load stops for this route
    stops = route.stops.all().order_by("sequence")
    
    context = {
        "user": user,
        "route": route,
        "stops": stops,
        "error": error,
    }
    
    return render(request, "zonaladmin/edit_route.html", context)

@login_required
def manage_stops(request, route_id):
    """
    View and manage stops for a specific route.
    Shows list of stops with add/edit/delete options.
    """
    user = request.user
    
    # Get route
    route = get_object_or_404(Route, id=route_id)
    
    # Zonal admin: ensure route belongs to their zone
    if getattr(user, "role", None) == "zonal_admin" and getattr(user, "zone_id", None):
        if route.zone_id != user.zone_id:
            messages.error(request, "You can only manage stops for routes in your zone.")
            return redirect("manage-routes")
    
    # Get all stops for this route ordered by sequence
    stops = route.stops.all().order_by("sequence")
    
    # Calculate next sequence number
    next_sequence = (stops.count() + 1) if stops.exists() else 1
    
    context = {
        "user": user,
        "route": route,
        "stops": stops,
        "next_sequence": next_sequence,
    }
    
    return render(request, "zonaladmin/manage_stops.html", context)


@login_required
def add_stop(request, route_id):
    """
    Add a new stop to a route.
    """
    user = request.user
    
    # Only admin and zonal_admin can add stops
    if not (user.is_superuser or getattr(user, "role", None) in ["admin", "zonal_admin"]):
        messages.error(request, "Permission denied.")
        return redirect("manage-routes")
    
    route = get_object_or_404(Route, id=route_id)
    
    # Zonal admin: ensure route belongs to their zone
    if getattr(user, "role", None) == "zonal_admin" and getattr(user, "zone_id", None):
        if route.zone_id != user.zone_id:
            messages.error(request, "You can only manage stops for routes in your zone.")
            return redirect("manage-routes")
    
    # Calculate next sequence
    next_sequence = route.stops.count() + 1
    
    if request.method == "POST":
        sequence = request.POST.get("sequence")
        name = request.POST.get("name", "").strip()
        distance_from_origin = request.POST.get("distance_from_origin")
        is_limited_stop = request.POST.get("is_limited_stop") == "on"
        
        # Validation
        if not all([sequence, name, distance_from_origin]):
            messages.error(request, "Sequence, name, and distance are required.")
            return redirect("manage-stops", route_id=route_id)
        
        try:
            sequence_int = int(sequence)
            distance_float = float(distance_from_origin)
            
            # Check if sequence already exists
            if route.stops.filter(sequence=sequence_int).exists():
                messages.error(request, f"Stop with sequence {sequence_int} already exists on this route.")
                return redirect("manage-stops", route_id=route_id)
            
            # Check if stop name already exists on this route
            if route.stops.filter(name=name).exists():
                messages.error(request, f"Stop named '{name}' already exists on this route.")
                return redirect("manage-stops", route_id=route_id)
            
            # Create stop
            Stop.objects.create(
                route=route,
                sequence=sequence_int,
                name=name,
                distance_from_origin=distance_float,
                is_limited_stop=is_limited_stop,
            )
            messages.success(request, f"Stop '{name}' added successfully!")
            return redirect("manage-stops", route_id=route_id)
            
        except ValueError:
            messages.error(request, "Invalid sequence or distance value.")
            return redirect("manage-stops", route_id=route_id)
        except Exception as e:
            messages.error(request, f"Error creating stop: {str(e)}")
            return redirect("manage-stops", route_id=route_id)
    
    context = {
        "user": user,
        "route": route,
        "next_sequence": next_sequence,
    }
    
    return render(request, "zonaladmin/add_stop.html", context)


@login_required
def edit_stop(request, route_id, stop_id):
    """
    Edit existing stop on a route.
    """
    user = request.user
    
    # Only admin and zonal_admin can edit stops
    if not (user.is_superuser or getattr(user, "role", None) in ["admin", "zonal_admin"]):
        messages.error(request, "Permission denied.")
        return redirect("manage-routes")
    
    route = get_object_or_404(Route, id=route_id)
    stop = get_object_or_404(Stop, id=stop_id, route=route)
    
    # Zonal admin: ensure route belongs to their zone
    if getattr(user, "role", None) == "zonal_admin" and getattr(user, "zone_id", None):
        if route.zone_id != user.zone_id:
            messages.error(request, "You can only manage stops for routes in your zone.")
            return redirect("manage-routes")
    
    if request.method == "POST":
        sequence = request.POST.get("sequence")
        name = request.POST.get("name", "").strip()
        distance_from_origin = request.POST.get("distance_from_origin")
        is_limited_stop = request.POST.get("is_limited_stop") == "on"
        
        # Validation
        if not all([sequence, name, distance_from_origin]):
            messages.error(request, "Sequence, name, and distance are required.")
            return redirect("manage-stops", route_id=route_id)
        
        try:
            sequence_int = int(sequence)
            distance_float = float(distance_from_origin)
            
            # Check if sequence is taken by another stop
            existing_seq = route.stops.filter(sequence=sequence_int).exclude(id=stop_id).first()
            if existing_seq:
                messages.error(request, f"Sequence {sequence_int} is already used by stop '{existing_seq.name}'.")
                return redirect("manage-stops", route_id=route_id)
            
            # Check if name is taken by another stop
            existing_name = route.stops.filter(name=name).exclude(id=stop_id).first()
            if existing_name:
                messages.error(request, f"Stop name '{name}' is already used on this route.")
                return redirect("manage-stops", route_id=route_id)
            
            # Update stop
            stop.sequence = sequence_int
            stop.name = name
            stop.distance_from_origin = distance_float
            stop.is_limited_stop = is_limited_stop
            stop.save()
            
            messages.success(request, f"Stop '{stop.name}' updated successfully!")
            return redirect("manage-stops", route_id=route_id)
            
        except ValueError:
            messages.error(request, "Invalid sequence or distance value.")
            return redirect("manage-stops", route_id=route_id)
        except Exception as e:
            messages.error(request, f"Error updating stop: {str(e)}")
            return redirect("manage-stops", route_id=route_id)
    
    context = {
        "user": user,
        "route": route,
        "stop": stop,
    }
    
    return render(request, "zonaladmin/edit_stop.html", context)


@login_required
def delete_stop(request, route_id, stop_id):
    """
    Delete a stop from a route.
    """
    user = request.user
    
    # Only admin and zonal_admin can delete stops
    if not (user.is_superuser or getattr(user, "role", None) in ["admin", "zonal_admin"]):
        messages.error(request, "Permission denied.")
        return redirect("manage-routes")
    
    route = get_object_or_404(Route, id=route_id)
    stop = get_object_or_404(Stop, id=stop_id, route=route)
    
    # Zonal admin: ensure route belongs to their zone
    if getattr(user, "role", None) == "zonal_admin" and getattr(user, "zone_id", None):
        if route.zone_id != user.zone_id:
            messages.error(request, "You can only manage stops for routes in your zone.")
            return redirect("manage-routes")
    
    if request.method == "POST":
        stop_name = stop.name
        
        # Check if this stop is used in any preinforms or demand alerts
        # (Optional: You may want to prevent deletion if stop is actively used)
        preinform_count = PreInform.objects.filter(
            boarding_stop=stop,
            status__in=["pending", "noted"]
        ).count()
        
        if preinform_count > 0:
            messages.warning(
                request, 
                f"Warning: {preinform_count} active pre-informs reference this stop. "
                f"Deleting anyway."
            )
        
        # Delete the stop
        stop.delete()
        messages.success(request, f"Stop '{stop_name}' deleted successfully!")
        return redirect("manage-stops", route_id=route_id)
    
    context = {
        "user": user,
        "route": route,
        "stop": stop,
    }
    
    return render(request, "zonaladmin/delete_stop.html", context)

@login_required
def all_routes_for_stops(request):
    """
    Show all routes so admin can select which route's stops to manage.
    This is the landing page when clicking "Stops" in header.
    """
    user = request.user
    
    # Get zone-filtered routes
    routes = filter_zone(Route.objects.all(), user).order_by("number")
    
    # Add stop count to each route
    from django.db.models import Count
    routes = routes.annotate(stop_count=Count('stops'))
    
    context = {
        "user": user,
        "routes": routes,
    }
    
    return render(request, "zonaladmin/all_routes_for_stops.html", context)
