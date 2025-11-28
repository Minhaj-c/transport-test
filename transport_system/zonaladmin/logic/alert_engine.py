# zonaladmin/logic/alert_engine.py

from django.utils import timezone
from django.db.models import Sum

from preinforms.models import PreInform
from demand.models import DemandAlert
from routes.models import Stop


def generate_demand_alerts(for_date=None, zone=None):
    """
    Generate / refresh demand alerts for one date + zone.

    ✅ Uses ONLY pre-informs with status = 'noted'
    ✅ Groups by boarding stop
    ✅ Creates DemandAlert rows with correct level
    """

    if for_date is None:
        for_date = timezone.localdate()

    # 1) Base queryset: ONLY NOTED pre-informs
    qs = PreInform.objects.filter(
        date_of_travel=for_date,
        status="noted",
    )

    # Restrict to zonal admin's zone (if given)
    if zone is not None:
        qs = qs.filter(route__zone=zone)

    # Nothing to do
    if not qs.exists():
        return []

    # 2) Group by stop and sum number of people
    grouped = (
        qs.values("boarding_stop")
          .annotate(total_people=Sum("passenger_count"))
    )

    created_alerts = []

    # Optional: clear previous system-generated alerts for this date+zone
    base_alerts = DemandAlert.objects.filter(
        created_at__date=for_date,
        admin_notes__icontains="Pre-Informs",
    )
    if zone is not None:
        base_alerts = base_alerts.filter(stop__route__zone=zone)
    base_alerts.delete()

    # 3) Create new alerts
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
            admin_notes=f"System (Pre-Informs) – auto from NOTED pre-informs for {for_date}. Total expected passengers: {count}.",
        )
        created_alerts.append(alert)

    return created_alerts
