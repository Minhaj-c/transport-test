# zonaladmin/logic/alert_engine.py

from django.utils import timezone
from django.db.models import Sum

from preinforms.models import PreInform
from demand.models import DemandAlert
from routes.models import Stop
from schedules.models import Schedule


# =========================================
# PART A: PRE-INFORM → DEMAND ALERT (existing)
# =========================================

def generate_demand_alerts(for_date=None, zone=None):
    """
    Generate / refresh demand alerts for one date (+ optionally one zone).

    ✅ Uses ONLY pre-informs with status = 'noted'
    ✅ Groups by boarding stop
    ✅ Sums passenger_count for each stop
    ✅ Creates DemandAlert rows (user=None -> system generated)
    ✅ Old system alerts (from pre-informs) for that date are deleted first
    """

    if for_date is None:
        for_date = timezone.localdate()

    # 1) Base queryset: ONLY NOTED pre-informs
    qs = PreInform.objects.filter(
        date_of_travel=for_date,
        status="noted",
    )

    # Optional: restrict to one zone
    if zone is not None:
        qs = qs.filter(route__zone=zone)

    # Nothing to process
    if not qs.exists():
        return []

    # 2) Group by stop and sum number of people
    grouped = (
        qs.values("boarding_stop")
          .annotate(total_people=Sum("passenger_count"))
    )

    created_alerts = []

    # 3) Clear previous system-generated alerts from pre-informs (same date [+ zone])
    base_alerts = DemandAlert.objects.filter(
        created_at__date=for_date,
        admin_notes__icontains="Pre-Informs",
    )
    if zone is not None:
        base_alerts = base_alerts.filter(stop__route__zone=zone)
    base_alerts.delete()

    # 4) Create new alerts
    for row in grouped:
        stop_id = row["boarding_stop"]
        count = row["total_people"]

        if stop_id is None:
            continue

        try:
            stop = Stop.objects.get(id=stop_id)
        except Stop.DoesNotExist:
            continue

        alert = DemandAlert.objects.create(
            user=None,  # system generated
            stop=stop,
            number_of_people=count,
            status="reported",
            admin_notes=(
                f"System (Pre-Informs) – auto from NOTED pre-informs "
                f"for {for_date}. Total expected passengers: {count}."
            ),
        )
        created_alerts.append(alert)

    return created_alerts


# =========================================
# PART B: BUS LOAD PREDICTION (new)
# =========================================

def compute_bus_load_for_schedule(schedule, include_pending=True, include_noted=True):
    """
    Core logic: for ONE schedule, calculate expected bus load stop-by-stop.

    Uses:
      - schedule.current_passengers  -> live passengers already inside bus
      - schedule.bus.capacity       -> max seats (no standing for now)
      - PreInforms on this route & date (pending/noted)

    Returns a dict like:
    {
      "schedule": schedule,
      "capacity": 40,
      "base_passengers": 10,
      "stops": [
         {
            "stop": Stop instance,
            "boarding": 5,
            "expected_load": 15,
            "over_capacity": False,
            "excess": 0,
         },
         ...
      ],
      "first_over_capacity_index": 3 or None,
    }
    """

    route = schedule.route
    bus = schedule.bus

    capacity = getattr(bus, "capacity", None) or 0
    base_passengers = getattr(schedule, "current_passengers", 0) or 0

    # 1) Get all stops on this route in correct order
    stops = list(
        Stop.objects.filter(route=route)
        .order_by("sequence")
    )

    # 2) Build queryset for preinforms on this route + date
    status_filters = []
    if include_pending:
        status_filters.append("pending")
    if include_noted:
        status_filters.append("noted")

    pre_qs = PreInform.objects.filter(
        route=route,
        date_of_travel=schedule.date,
        status__in=status_filters or ["pending", "noted"],
    )

    # Sum passengers for each stop
    pre_grouped = (
        pre_qs.values("boarding_stop")
        .annotate(total_people=Sum("passenger_count"))
    )
    pre_by_stop = {
        row["boarding_stop"]: row["total_people"] for row in pre_grouped
    }

    # 3) Iterate stops and compute cumulative load
    results = []
    running_load = base_passengers
    first_over_idx = None

    for idx, stop in enumerate(stops):
        boarding = pre_by_stop.get(stop.id, 0) or 0

        # For now we ignore people getting down (alighting)
        running_load += boarding

        over = running_load > capacity if capacity > 0 else False
        excess = max(0, running_load - capacity) if capacity > 0 else 0

        if over and first_over_idx is None:
            first_over_idx = idx

        results.append(
            {
                "stop": stop,
                "boarding": boarding,
                "expected_load": running_load,
                "over_capacity": over,
                "excess": excess,
            }
        )

    return {
        "schedule": schedule,
        "capacity": capacity,
        "base_passengers": base_passengers,
        "stops": results,
        "first_over_capacity_index": first_over_idx,
    }


def compute_bus_load_for_date_zone(for_date=None, zone=None):
    """
    Helper to run prediction for ALL schedules in one date (+ zone).

    Returns list of prediction dicts (same structure as compute_bus_load_for_schedule).
    """

    if for_date is None:
        for_date = timezone.localdate()

    schedules = Schedule.objects.filter(date=for_date)

    if zone is not None:
        schedules = schedules.filter(route__zone=zone)

    predictions = []

    for sch in schedules.select_related("route", "bus", "driver"):
        predictions.append(compute_bus_load_for_schedule(sch))

    return predictions


def debug_print_bus_load_for_schedule(schedule):
    """
    Simple debug printer for Django shell usage.
    Doesn't affect DB. Just prints expected load per stop.
    """

    data = compute_bus_load_for_schedule(schedule)
    print(f"\n=== Bus Load Prediction for Schedule #{schedule.id} ===")
    print(f"Route: {schedule.route.number} – {schedule.route.name}")
    print(f"Date: {schedule.date}")
    print(f"Bus: {schedule.bus.number_plate} (capacity {data['capacity']})")
    print(f"Base passengers already inside: {data['base_passengers']}")
    print("---------------------------------------------------")

    for row in data["stops"]:
        stop = row["stop"]
        boarding = row["boarding"]
        load = row["expected_load"]
        over = row["over_capacity"]
        excess = row["excess"]

        flag = ""
        if over:
            flag = f"  >>> OVER by {excess}"

        print(
            f"Stop {stop.sequence}: {stop.name:25} | "
            f"boarding +{boarding:2d} | expected load = {load:3d}{flag}"
        )

    idx = data["first_over_capacity_index"]
    if idx is not None:
        stop = data["stops"][idx]["stop"]
        print(
            f"\n⚠ Bus expected to exceed capacity after stop "
            f"{stop.sequence} ({stop.name})."
        )
    else:
        print("\n✅ Bus never exceeds capacity on this route with current data.")


# zonaladmin/logic/alert_engine.py

def get_overflow_warnings_for_schedule(schedule):
    """
    Small helper to summarize where the bus will overflow
    using compute_bus_load_for_schedule().
    """
    data = compute_bus_load_for_schedule(schedule)

    capacity = data["capacity"]
    stops_info = data["stops"]

    warnings = []
    for row in stops_info:
        stop = row["stop"]
        expected = row["expected_load"]
        if expected > capacity:
            warnings.append(
                {
                    "stop": stop,
                    "expected_load": expected,
                    "extra": expected - capacity,
                }
            )

    return {
        "schedule": data["schedule"],
        "route": data["route"],
        "capacity": capacity,
        "base_inside": data["base_inside"],
        "stops": stops_info,
        "will_overflow": data["will_overflow"],
        "first_overflow_stop": data["first_overflow_stop"],
        "overflow_amount": data["overflow_amount"],
        "warnings": warnings,
    }


def compute_bus_load_for_schedule(schedule):
    """
    For ONE schedule:
    - Start from current_passengers (driver app)
    - Add NOTED pre-informs per stop (for this route + date)
    - Return per-stop expected load and max load
    """
    from django.db.models import Sum

    route = schedule.route
    date = schedule.date

    # Capacity: prefer schedule.total_seats, else bus.capacity, else 40
    capacity = (
        schedule.total_seats
        or getattr(schedule.bus, "capacity", None)
        or 40
    )

    base_passengers = schedule.current_passengers or 0

    # Only NOTED pre-informs for this date+route
    qs = PreInform.objects.filter(
        route=route,
        date_of_travel=date,
        status="noted",
    )

    # Group by stop, ordered by route sequence
    grouped = (
        qs.values(
            "boarding_stop",
            "boarding_stop__name",
            "boarding_stop__sequence",
        )
        .annotate(total_people=Sum("passenger_count"))
        .order_by("boarding_stop__sequence")
    )

    rows = []
    running = base_passengers
    max_load = base_passengers

    for row in grouped:
        stop_id = row["boarding_stop"]
        stop_name = row["boarding_stop__name"] or "Unknown stop"
        seq = row["boarding_stop__sequence"] or 0
        boarding = row["total_people"] or 0

        running += boarding
        max_load = max(max_load, running)

        rows.append(
            {
                "stop_id": stop_id,
                "stop_name": stop_name,
                "sequence": seq,
                "boarding": boarding,
                "expected_load": running,
                "over_capacity": running > capacity,
                "ratio": (running / capacity) if capacity else None,
            }
        )

    return {
        "schedule": schedule,
        "capacity": capacity,
        "base_passengers": base_passengers,
        "rows": rows,
        "max_load": max_load,
    }


def debug_print_bus_load_for_schedule(schedule):
    data = compute_bus_load_for_schedule(schedule)
    route = schedule.route
    cap = data["capacity"]

    print(f"=== Bus Load Prediction for Schedule #{schedule.id} ===")
    print(f"Route: {route.number} – {route.name}")
    print(f"Date:  {schedule.date}")
    print(f"Bus:   {schedule.bus.number_plate} (capacity {cap})")
    print(f"Base passengers already inside: {data['base_passengers']}")
    print("-" * 55)

    if not data["rows"]:
        print("No NOTED pre-informs for this schedule.")
        return

    for row in data["rows"]:
        print(
            f"Stop {row['sequence']}: {row['stop_name']:<25} | "
            f"boarding +{row['boarding']:2d} | "
            f"expected load = {row['expected_load']:3d}"
        )

    if data["max_load"] > cap:
        print(
            f"\n⚠️  Bus will exceed capacity! Max load = "
            f"{data['max_load']} / {cap}"
        )
    else:
        print(
            f"\n✅ Bus never exceeds capacity on this route with current data "
            f"(max load = {data['max_load']} / {cap})."
        )


def generate_prediction_alerts(for_date=None, zone=None):
    """
    NEW: Prediction-based demand alerts.

    - Looks at *running* buses (bus.is_running = True)
    - For each schedule, predicts load per stop
    - If expected_load >= capacity (or very close), creates DemandAlert

    These alerts are separate from "System (Pre-Informs)" alerts.
    """
    from schedules.models import Schedule

    if for_date is None:
        for_date = timezone.localdate()

    # Base queryset: today's schedules whose buses are running
    qs = Schedule.objects.select_related("bus", "route").filter(
        date=for_date,
        bus__is_running=True,
    )

    if zone is not None:
        qs = qs.filter(route__zone=zone)

    if not qs.exists():
        return []

    # Clear old prediction-based alerts for this date+zone
    base_alerts = DemandAlert.objects.filter(
        created_at__date=for_date,
        admin_notes__icontains="Prediction:",
    )
    if zone is not None:
        base_alerts = base_alerts.filter(stop__route__zone=zone)
    base_alerts.delete()

    created = []

    for schedule in qs:
        data = compute_bus_load_for_schedule(schedule)
        cap = data["capacity"]

        for row in data["rows"]:
            stop_id = row["stop_id"]
            load = row["expected_load"]
            ratio = row["ratio"] or 0.0

            # Threshold:
            #  - if load > capacity  -> CRITICAL (definitely full)
            #  - if ratio >= 0.9     -> HIGH (90%+ full)
            if load <= 0:
                continue

            if load > cap:
                level = "critical"
            elif ratio >= 0.9:
                level = "high"
            else:
                continue  # no alert for normal/medium predictions

            try:
                stop = Stop.objects.get(id=stop_id)
            except Stop.DoesNotExist:
                continue

            note = (
                f"Prediction: Bus on schedule #{schedule.id} for route "
                f"{schedule.route.number} is expected to reach {level.upper()} load "
                f"at stop '{row['stop_name']}' "
                f"(expected {load} passengers, capacity {cap}). "
                f"Base inside bus: {data['base_passengers']}. "
                f"Source: NOTED pre-informs for {for_date}."
            )

            alert = DemandAlert.objects.create(
                user=None,              # system-generated
                stop=stop,
                number_of_people=load,  # predicted load at this stop
                status="reported",
                admin_notes=note,
            )
            created.append(alert)

    return created
