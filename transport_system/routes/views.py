"""
Routes API Views
"""

from rest_framework import generics, status
from rest_framework.decorators import api_view,permission_classes
from rest_framework.response import Response

from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from .models import Route, Stop
from .serializers import RouteSerializer, RouteListSerializer, StopSerializer

# Extra models for dashboard stats
from schedules.models import Schedule, Bus
from preinforms.models import PreInform
from demand.models import DemandAlert
from rest_framework.permissions import IsAuthenticated
from datetime import datetime


@api_view(['GET'])
def api_welcome(request):
    """
    Welcome message for API root

    GET /api/
    """
    return Response({
        'message': 'Welcome to Transport Management API',
        'version': '1.0',
        'endpoints': {
            'auth': {
                'signup': '/api/signup/',
                'login': '/api/login/',
                'logout': '/api/logout/',
                'profile': '/api/profile/',
            },
            'routes': {
                'list': '/api/routes/',
                'detail': '/api/routes/<id>/',
                'stops': '/api/routes/<id>/stops/',
            },
            'schedules': {
                'list': '/api/schedules/',
                'driver': '/api/schedules/driver/',
            },
            'preinforms': {
                'create': '/api/preinforms/',
                'list': '/api/preinforms/',
            },
            'demand': {
                'create': '/api/demand-alerts/',
                'list': '/api/demand-alerts/',
            },
        }
    })


class RouteListView(generics.ListAPIView):
    """
    API view to list all bus routes

    GET /api/routes/
    """
    queryset = Route.objects.all().prefetch_related('stops')
    serializer_class = RouteSerializer

    def get_queryset(self):
        """
        Optionally filter routes by origin or destination
        """
        queryset = super().get_queryset()

        origin = self.request.query_params.get('origin')
        destination = self.request.query_params.get('destination')

        if origin:
            queryset = queryset.filter(origin__icontains=origin)
        if destination:
            queryset = queryset.filter(destination__icontains=destination)

        return queryset


class RouteDetailView(generics.RetrieveAPIView):
    """
    API view to get single route details

    GET /api/routes/<id>/
    """
    queryset = Route.objects.all().prefetch_related('stops')
    serializer_class = RouteSerializer


@api_view(['GET'])
def route_stops_view(request, route_id):
    """
    API view to get all stops for a specific route

    GET /api/routes/<route_id>/stops/
    """
    try:
        route = Route.objects.get(id=route_id)
        stops = route.stops.all().order_by('sequence')
        serializer = StopSerializer(stops, many=True)

        return Response({
            'route': {
                'id': route.id,
                'number': route.number,
                'name': route.name
            },
            'stops': serializer.data
        })
    except Route.DoesNotExist:
        return Response(
            {'error': 'Route not found'},
            status=status.HTTP_404_NOT_FOUND
        )




@api_view(["GET"])
@permission_classes([IsAuthenticated])
def route_live_status_view(request, route_id):
    """
    Get predicted live crowd + ETA for a specific route and stop.

    GET /api/routes/<route_id>/live-status/?stop_id=5&date=2025-12-01

    Query params:
      - stop_id       (required if stop_sequence not provided)
      - stop_sequence (optional alternative)
      - date          (optional, YYYY-MM-DD, default: today)
    """
    from schedules.views import compute_future_load_for_schedule  # lazy import to avoid circular
    from schedules.models import Schedule
    from routes.models import Route, Stop

    # 1) Validate route
    try:
        route = Route.objects.get(id=route_id)
    except Route.DoesNotExist:
        return Response(
            {"detail": "Route not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # 2) Parse date
    date_str = request.GET.get("date")
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        target_date = timezone.now().date()

    # 3) Determine target stop / sequence
    stop_id = request.GET.get("stop_id")
    stop_sequence_param = request.GET.get("stop_sequence")

    if not stop_id and not stop_sequence_param:
        return Response(
            {"detail": "Either stop_id or stop_sequence is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    target_stop = None
    target_seq = None

    if stop_id:
        try:
            target_stop = route.stops.get(id=stop_id)
            target_seq = target_stop.sequence
        except Stop.DoesNotExist:
            return Response(
                {"detail": "Stop does not belong to this route."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        # Using sequence directly
        try:
            target_seq = int(stop_sequence_param)
            if target_seq <= 0:
                raise ValueError
        except ValueError:
            return Response(
                {"detail": "Invalid stop_sequence."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Try to find stop object (optional)
        target_stop = (
            route.stops.filter(sequence=target_seq).first()
        )

    # 4) Get all schedules for this route + date
    schedules_qs = (
        Schedule.objects
        .filter(route=route, date=target_date)
        .select_related("bus", "driver")
        .order_by("departure_time")
    )

    if not schedules_qs.exists():
        return Response(
            {
                "route": {
                    "id": route.id,
                    "number": route.number,
                    "name": route.name,
                    "origin": route.origin,
                    "destination": route.destination,
                },
                "date": str(target_date),
                "target_stop": {
                    "id": getattr(target_stop, "id", None),
                    "name": getattr(target_stop, "name", None),
                    "sequence": target_seq,
                },
                "buses": [],
            },
            status=status.HTTP_200_OK,
        )

    # 5) Build result per schedule
    MINUTES_PER_STOP = 3  # simple heuristic for ETA
    buses_data = []

    for schedule in schedules_qs:
        # Compute forecast using helper we already wrote
        forecast = compute_future_load_for_schedule(schedule)

        capacity = forecast.get("capacity") or 0
        current_passengers = forecast.get("current_passengers") or 0
        current_seq = forecast.get("current_stop_sequence") or 0

        # Find predicted passengers at the target stop
        predicted_at_stop = None

        # if bus already passed or at this stop, treat current_passengers as load
        if target_seq <= current_seq:
            predicted_at_stop = current_passengers
            stops_away = max(current_seq - target_seq, 0) * -1  # negative means already passed
        else:
            # look into future_stops
            future_stops = forecast.get("future_stops", [])
            for fs in future_stops:
                if fs.get("sequence") == target_seq:
                    predicted_at_stop = fs.get("predicted_after")
                    break

            if predicted_at_stop is None:
                # This bus never reaches that stop (e.g. short-turned)
                continue

            stops_away = target_seq - current_seq

        # Fallback if capacity missing
        if capacity <= 0:
            capacity = schedule.total_seats or (schedule.bus.capacity if schedule.bus else 0)

        occupied = predicted_at_stop or 0
        available = max(capacity - occupied, 0)
        occupancy_rate = 0.0
        if capacity > 0:
            occupancy_rate = (occupied / capacity) * 100.0

        # Simple ETA in minutes (only if bus still to come)
        if stops_away <= 0:
            eta_minutes = 0
        else:
            eta_minutes = stops_away * MINUTES_PER_STOP

        bus_obj = schedule.bus
        buses_data.append({
            "schedule_id": schedule.id,
            "bus_id": bus_obj.id if bus_obj else None,
            "bus_number": bus_obj.number_plate if bus_obj else None,
            "is_spare_trip": bool(getattr(schedule, "is_spare_trip", False)),
            "capacity": capacity,
            "current_stop_sequence": current_seq,
            "stops_away": stops_away,          # 0 = at stop, negative = already passed
            "eta_minutes": eta_minutes,        # 0 if at / past stop
            "predicted_passengers_at_stop": occupied,
            "available_seats_at_stop": available,
            "occupancy_rate_at_stop": occupancy_rate,
            "will_overflow_later": forecast.get("will_overflow", False),
            "overflow_from_stop_sequence": forecast.get("overflow_from_stop_sequence"),
            "is_running": getattr(bus_obj, "is_running", None),
        })

    # sort: nearest first by ETA, then more seats available
    buses_data.sort(key=lambda b: (max(b["eta_minutes"], 0), -b["available_seats_at_stop"]))

    return Response(
        {
            "route": {
                "id": route.id,
                "number": route.number,
                "name": route.name,
                "origin": route.origin,
                "destination": route.destination,
            },
            "date": str(target_date),
            "target_stop": {
                "id": getattr(target_stop, "id", None),
                "name": getattr(target_stop, "name", None),
                "sequence": target_seq,
            },
            "buses": buses_data,
        },
        status=status.HTTP_200_OK,
    )




@login_required
def homepage(request):
    """
    Main frontend / control page.

    - If user.role == 'admin' → show full admin dashboard
    - Otherwise → show limited 'Useful endpoints' view
    """
    is_admin = getattr(request.user, "role", "") == "admin"

    # Base context always available
    context = {
        "user": request.user,
        "is_admin": is_admin,
    }

    if is_admin:
        today = timezone.now().date()

        # Stats for cards
        total_routes = Route.objects.count()
        total_buses = Bus.objects.count()
        today_schedules = Schedule.objects.filter(date=today).count()
        upcoming_schedules = Schedule.objects.filter(date__gte=today).count()

        active_preinforms = PreInform.objects.filter(
            date_of_travel__gte=today,
            status__in=["pending", "noted"],
        ).count()

        active_demand_alerts = DemandAlert.objects.filter(
            expires_at__gt=timezone.now(),
            status__in=["reported", "verified", "dispatched"],
        ).count()

        # Recent records (tables)
        recent_preinforms = PreInform.objects.select_related(
            "route", "boarding_stop", "user"
        ).order_by("-created_at")[:5]

        recent_demand = DemandAlert.objects.select_related(
            "stop", "stop__route", "user"
        ).order_by("-created_at")[:5]

        context.update({
            "today": today,
            "total_routes": total_routes,
            "total_buses": total_buses,
            "today_schedules": today_schedules,
            "upcoming_schedules": upcoming_schedules,
            "active_preinforms": active_preinforms,
            "active_demand_alerts": active_demand_alerts,
            "recent_preinforms": recent_preinforms,
            "recent_demand": recent_demand,
        })

    return render(request, "homepage.html", context)
