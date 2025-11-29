# zonaladmin/logic/alert_engine.py

from django.utils import timezone
from django.db.models import Sum

from preinforms.models import PreInform
from demand.models import DemandAlert
from routes.models import Stop
from schedules.models import Schedule


PREINFORM_NOTE = "System (Pre-Informs) – auto from NOTED pre-informs"
PREDICTION_NOTE_PREFIX = "Prediction (Bus load) – "


# =====================================================
# A. OLD BEHAVIOUR – PRE-INFORMS → DEMAND ALERTS
# =====================================================

def _group_noted_preinforms(for_date, zone=None):
    qs = PreInform.objects.filter(
        date_of_travel=for_date,
        status="noted",
    )

    if zone is not None:
        qs = qs.filter(route__zone=zone)

    grouped = qs.values("boarding_stop").annotate(
        total_people=Sum("passenger_count")
    )
    return qs, grouped


def generate_preinform_alerts(for_date=None, zone=None):
    """
    Old system:

    - Take ONLY NOTED pre-informs
    - Group by boarding_stop
    - Sum passenger_count
    - Create DemandAlert rows with admin_notes mentioning "Pre-Informs"
    """

    if for_date is None:
        for_date = timezone.localdate()

    qs, grouped = _group_noted_preinforms(for_date, zone)

    # Clear old pre-inform alerts for that date (+zone)
    alerts_qs = DemandAlert.objects.filter(
        created_at__date=for_date,
        admin_notes__icontains="Pre-Informs",
    )
    if zone is not None:
        alerts_qs = alerts_qs.filter(stop__route__zone=zone)
    alerts_qs.delete()

    if not qs.exists():
        return []

    created = []

    for row in grouped:
        stop_id = row["boarding_stop"]
        count = row["total_people"]

        if not stop_id:
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
                f"{PREINFORM_NOTE} for {for_date}. "
                f"Total expected passengers: {count}."
            ),
        )
        created.append(alert)

    return created


# =====================================================
# B. BUS LOAD PREDICTION (LIVE BUS + NOTED PRE-INFORMS)
# =====================================================

def compute_bus_load_for_schedule(schedule):
    """
    For ONE schedule:
    - Start from schedule.current_passengers
    - Add NOTED pre-informs per stop (for this route + date)
    - Return per-stop expected load, max load and first overflow stop
    """

    route = schedule.route
    date = schedule.date

    # Capacity: prefer schedule.total_seats, else bus.capacity
    capacity = (
        schedule.total_seats
        or getattr(schedule.bus, "capacity", None)
    )

    base = schedule.current_passengers or 0

    # All stops in order
    stops = list(
        Stop.objects.filter(route=route).order_by("sequence")
    )

    # NOTED pre-informs for this route + date
    pis = PreInform.objects.filter(
        route=route,
        date_of_travel=date,
        status="noted",
    )

    boarding_by_stop = (
        pis.values("boarding_stop")
           .annotate(total=Sum("passenger_count"))
    )
    boarding_map = {
        row["boarding_stop"]: row["total"] for row in boarding_by_stop
    }

    load = base
    max_load = base
    overflow_stop = None
    stop_data = []

    for st in stops:
        boarding = boarding_map.get(st.id, 0) or 0
        load += boarding

        if load > max_load:
            max_load = load

        if overflow_stop is None and capacity is not None and load > capacity:
            overflow_stop = st

        stop_data.append(
            {
                "stop": st,
                "boarding": boarding,
                "expected_load": load,
            }
        )

    return {
        "schedule": schedule,
        "route": route,
        "capacity": capacity,
        "base_passengers": base,
        "stops": stop_data,
        "max_load": max_load,
        "overflow_stop": overflow_stop,
    }


def debug_print_bus_load_for_schedule(schedule):
    """
    Helper for Django shell (does NOT touch DB).
    """

    data = compute_bus_load_for_schedule(schedule)

    route = data["route"]
    capacity = data["capacity"]
    base = data["base_passengers"]

    print(f"=== Bus Load Prediction for Schedule #{schedule.id} ===")
    print(f"Route: {route.number} – {route.name}")
    print(f"Date: {schedule.date}")
    print(f"Bus: {schedule.bus.number_plate if schedule.bus else 'N/A'} "
          f"(capacity {capacity})")
    print(f"Base passengers already inside: {base}")
    print("-" * 55)

    for idx, row in enumerate(data["stops"], start=1):
        stop = row["stop"]
        boarding = row["boarding"]
        expected = row["expected_load"]
        print(
            f"Stop {idx}: {stop.name:25} | "
            f"boarding +{boarding:2d} | expected load = {expected:3d}"
        )

    if data["overflow_stop"] and capacity is not None:
        print(
            f"\n⚠ Overflow at stop '{data['overflow_stop'].name}' – "
            f"max load {data['max_load']} > capacity {capacity}"
        )
    else:
        print(
            "\n✅ Bus never exceeds capacity on this route "
            "with current data."
        )


# =====================================================
# C. PREDICTION-BASED DEMAND ALERTS
# =====================================================

def generate_prediction_alerts(for_date=None, zone=None):
    """
    NEW:

    - For each schedule on given date (+zone)
    - Compute expected load at each stop
    - If expected_load > capacity at some stop,
      create ONE DemandAlert for the FIRST overflow stop.
    """

    if for_date is None:
        for_date = timezone.localdate()

    qs = Schedule.objects.filter(date=for_date).select_related(
        "route", "bus", "driver"
    )
    if zone is not None:
        qs = qs.filter(route__zone=zone)

    # Clear old prediction alerts for that date (+zone)
    alerts_qs = DemandAlert.objects.filter(
        created_at__date=for_date,
        admin_notes__icontains="Prediction (Bus load)",
    )
    if zone is not None:
        alerts_qs = alerts_qs.filter(stop__route__zone=zone)
    alerts_qs.delete()

    created = []

    for sch in qs:
        data = compute_bus_load_for_schedule(sch)
        capacity = data["capacity"]
        if capacity is None:
            continue  # can’t predict without capacity

        for row in data["stops"]:
            if row["expected_load"] <= capacity:
                continue

            stop = row["stop"]
            expected = row["expected_load"]

            alert = DemandAlert.objects.create(
                user=None,
                stop=stop,
                number_of_people=expected,
                status="reported",
                admin_notes=(
                    f"{PREDICTION_NOTE_PREFIX}"
                    f"Route {sch.route.number}, Bus {sch.bus.number_plate} "
                    f"is expected to carry {expected} passengers "
                    f"(capacity {capacity}) after stop '{stop.name}' "
                    f"on {for_date}."
                ),
            )
            created.append(alert)

            # only first overflow stop per schedule
            break

    return created


# =====================================================
# D. PUBLIC ENTRY POINT (used by zonal_demand_alerts)
# =====================================================

def generate_demand_alerts(for_date=None, zone=None):
    """
    This is what zonal_demand_alerts() calls.

    - Keeps OLD behaviour (pre-inform alerts)
    - Adds NEW prediction-based alerts
    """

    pre = generate_preinform_alerts(for_date=for_date, zone=zone)
    pred = generate_prediction_alerts(for_date=for_date, zone=zone)
    return pre + pred
def get_overflow_warnings_for_schedule(schedule):
    """
    Backwards-compatible helper so old imports keep working.

    Returns a summary dict with all stops and the ones where the bus
    is expected to go over capacity.
    """
    data = compute_bus_load_for_schedule(schedule)
    cap = data["capacity"] or 0

    warnings = []
    for row in data["stops"]:
        expected = row["expected_load"]
        if cap and expected > cap:
            warnings.append(
                {
                    "stop": row["stop"],
                    "expected_load": expected,
                    "extra": expected - cap,
                }
            )

    return {
        "schedule": schedule,
        "route": data["route"],
        "capacity": cap,
        "base_passengers": data["base_passengers"],
        "stops": data["stops"],
        "warnings": warnings,
    }
