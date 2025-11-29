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
