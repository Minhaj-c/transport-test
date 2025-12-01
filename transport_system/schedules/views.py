from django.shortcuts import render, get_object_or_404

"""
Schedules API Views
"""

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
import math
from django.views.decorators.csrf import csrf_exempt

from .models import Schedule, Bus
from .serializers import ScheduleSerializer, LiveBusSerializer, BusLocationSerializer
from routes.models import Route
from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication that skips CSRF checks.

    Needed for native/mobile apps that use cookies but can't send CSRF tokens.
    """
    def enforce_csrf(self, request):
        return  # disable CSRF check


# ==========================
#  BASIC SCHEDULE / BUS API
# ==========================

class ScheduleListView(generics.ListAPIView):
    """
    API view to list schedules
    
    GET /api/schedules/
    Optional params:
    - route_id: Filter by route
    - date: Filter by date (YYYY-MM-DD)
    - driver_id: Filter by driver
    """
    serializer_class = ScheduleSerializer
    
    def get_queryset(self):
        queryset = Schedule.objects.all().select_related('route', 'bus', 'driver')
        
        # Get filter parameters
        route_id = self.request.query_params.get('route_id')
        date = self.request.query_params.get('date')
        driver_id = self.request.query_params.get('driver_id')
        
        # Apply filters
        if route_id:
            queryset = queryset.filter(route_id=route_id)
        if date:
            queryset = queryset.filter(date=date)
        else:
            # Default to today and future schedules
            today = timezone.now().date()
            queryset = queryset.filter(date__gte=today)
        if driver_id:
            queryset = queryset.filter(driver_id=driver_id)
        
        return queryset.order_by('date', 'departure_time')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def driver_schedules_view(request):
    """
    API view to get schedules for logged-in driver
    
    GET /api/schedules/driver/
    """
    if getattr(request.user, "role", None) != 'driver':
        return Response(
            {'error': 'Only drivers can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    today = timezone.now().date()
    schedules = (
        Schedule.objects
        .filter(driver=request.user, date__gte=today)
        .select_related('route', 'bus')
        .order_by('date', 'departure_time')
    )
    
    serializer = ScheduleSerializer(schedules, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def nearby_buses(request):
    """
    Get buses near user location
    
    GET /api/buses/nearby/?latitude=11.2588&longitude=75.7804&radius=5
    """
    try:
        user_lat = float(request.GET.get('latitude'))
        user_lng = float(request.GET.get('longitude'))
        radius_km = float(request.GET.get('radius', 5))
    except (TypeError, ValueError):
        return Response(
            {'error': 'Invalid coordinates. Provide latitude, longitude, and optional radius.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    five_minutes_ago = timezone.now() - timedelta(minutes=5)
    
    running_buses = (
        Bus.objects
        .filter(
            is_running=True,
            current_latitude__isnull=False,
            current_longitude__isnull=False,
            last_location_update__gte=five_minutes_ago,
        )
        .select_related('current_route', 'current_schedule')
    )
    
    nearby_buses_list = []
    
    for bus in running_buses:
        distance = calculate_distance(
            user_lat,
            user_lng,
            float(bus.current_latitude),
            float(bus.current_longitude),
        )
        
        if distance <= radius_km:
            bus_data = LiveBusSerializer(bus).data
            bus_data['distance_km'] = round(distance, 2)
            nearby_buses_list.append(bus_data)
    
    nearby_buses_list.sort(key=lambda x: x['distance_km'])
    
    return Response(
        {
            'buses': nearby_buses_list,
            'user_location': {'latitude': user_lat, 'longitude': user_lng},
            'search_radius_km': radius_km,
            'total_found': len(nearby_buses_list),
        }
    )


@csrf_exempt
@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def update_bus_location(request):
    """
    Driver updates bus GPS location and marks bus/schedule as running.

    POST /api/buses/update-location/
    {
        "bus_id": 1,
        "latitude": 11.874321,
        "longitude": 75.370123,
        "schedule_id": 12
    }
    """
    user = request.user
    data = request.data

    bus_id = data.get("bus_id")
    lat = data.get("latitude")
    lng = data.get("longitude")
    schedule_id = data.get("schedule_id")

    # 🔍 DEBUG PRINTS
    print("=== update_bus_location DEBUG ===")
    print(
        "Logged in user -> id:", user.id,
        "| email:", getattr(user, "email", None),
        "| role:", getattr(user, "role", None),
    )
    print("Payload -> bus_id:", bus_id, "| schedule_id:", schedule_id, "| lat:", lat, "| lng:", lng)

    if not all([bus_id, lat, lng, schedule_id]):
        print("❌ Missing fields in payload")
        return Response(
            {"detail": "bus_id, latitude, longitude and schedule_id are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    bus = get_object_or_404(Bus, id=bus_id)
    schedule = get_object_or_404(
        Schedule.objects.select_related("route", "driver"),
        id=schedule_id,
    )

    print(
        "Schedule in DB -> id:", schedule.id,
        "| driver_id:", schedule.driver_id,
        "| driver_email:", schedule.driver.email,
    )

    if schedule.driver_id != user.id and not user.is_superuser:
        print("❌ PERMISSION DENIED: schedule.driver_id != user.id")
        return Response(
            {"detail": "Only the assigned driver can update location."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        print("❌ Invalid latitude/longitude:", lat, lng)
        return Response(
            {"detail": "Invalid latitude/longitude."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    bus.current_latitude = lat
    bus.current_longitude = lng
    bus.last_location_update = timezone.now()
    bus.is_running = True
    bus.current_route = schedule.route
    bus.current_schedule = schedule
    bus.save(
        update_fields=[
            "current_latitude",
            "current_longitude",
            "last_location_update",
            "is_running",
            "current_route",
            "current_schedule",
        ]
    )

    print("✅ Location updated OK for bus", bus.id, "| schedule", schedule.id)

    return Response(
        {"success": True, "message": "Bus location updated."}
    )


@api_view(['GET'])
def bus_details(request, bus_id):
    """
    Get detailed information about a specific running bus.
    """
    try:
        bus = (
            Bus.objects
            .select_related('current_route', 'current_schedule')
            .get(id=bus_id, is_running=True)
        )
        return Response(LiveBusSerializer(bus).data)
    except Bus.DoesNotExist:
        return Response(
            {'error': 'Bus not found or not running'},
            status=status.HTTP_404_NOT_FOUND,
        )


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two coordinates using Haversine formula.
    Returns distance in kilometers.
    """
    R = 6371  # km
    
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c
    
    return distance


def schedules_page(request):
    """
    Serve the schedules frontend page.
    """
    route_id = request.GET.get('route_id')
    context = {'route_id': route_id}
    return render(request, 'schedules.html', context)


# ==========================
#  LIVE PASSENGERS + STOP
# ==========================

@csrf_exempt
@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def update_passenger_count(request):
    """
    Driver updates live passenger count for a schedule.

    POST /api/schedules/passenger-count/
    {
        "schedule_id": 7,
        "count": 12
    }
    """
    user = request.user
    schedule_id = request.data.get("schedule_id")
    count = request.data.get("count")

    print("=== update_passenger_count DEBUG ===")
    print("User:", user.id, getattr(user, "email", None))
    print("Raw payload:", request.data)

    if schedule_id is None or count is None:
        print("❌ Missing schedule_id or count")
        return Response(
            {"detail": "schedule_id and count are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        count = int(count)
        if count < 0:
            raise ValueError
    except ValueError:
        print("❌ Invalid count:", count)
        return Response(
            {"detail": "Invalid count value."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    schedule = get_object_or_404(
        Schedule.objects.select_related("driver", "bus"),
        id=schedule_id,
    )

    print(
        "Schedule in DB -> id:", schedule.id,
        "| driver_id:", schedule.driver_id,
        "| driver_email:", getattr(schedule.driver, "email", None),
        "| old current_passengers:", getattr(schedule, "current_passengers", None),
    )

    if schedule.driver_id != user.id and not user.is_superuser:
        print("❌ PERMISSION DENIED for user", user.id)
        return Response(
            {"detail": "Only the assigned driver can update passenger count."},
            status=status.HTTP_403_FORBIDDEN,
        )

    schedule.set_passenger_count(count)

    print(
        "✅ Passenger count updated ->",
        "current_passengers:", getattr(schedule, "current_passengers", None),
        "| available_seats:", getattr(schedule, "available_seats", None),
    )

    return Response(
        {
            "success": True,
            "message": "Passenger count updated.",
            "current_passengers": getattr(schedule, "current_passengers", None),
            "available_seats": getattr(schedule, "available_seats", None),
        }
    )
    
    
@csrf_exempt 
@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def update_current_stop(request):
    """
    Driver updates the CURRENT STOP of a running schedule.

    POST /api/schedules/current-stop/
    {
        "schedule_id": 7,
        "stop_sequence": 3
    }
    """
    user = request.user
    schedule_id = request.data.get("schedule_id")
    stop_sequence = request.data.get("stop_sequence")

    if schedule_id is None or stop_sequence is None:
        return Response(
            {"detail": "schedule_id and stop_sequence are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        stop_sequence = int(stop_sequence)
        if stop_sequence <= 0:
            raise ValueError
    except ValueError:
        return Response(
            {"detail": "Invalid stop_sequence value."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    schedule = get_object_or_404(
        Schedule.objects.select_related("driver", "bus", "route"),
        id=schedule_id,
    )

    if schedule.driver_id != user.id and not user.is_superuser:
        return Response(
            {"detail": "Only the assigned driver can update current stop."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # 🔒 NEW: don't allow moving the bus backwards
    old_seq = schedule.current_stop_sequence or 0
    if stop_sequence < old_seq:
        # Ignore backward update – keep existing value
        return Response(
            {
                "success": False,
                "message": (
                    "Ignored update: stop_sequence "
                    f"{stop_sequence} is less than current_stop_sequence {old_seq}."
                ),
                "current_stop_sequence": old_seq,
                "schedule": ScheduleSerializer(schedule).data,
            },
            status=status.HTTP_200_OK,
        )

    schedule.current_stop_sequence = stop_sequence
    schedule.save(update_fields=["current_stop_sequence"])

    return Response(
        {
            "success": True,
            "message": "Current stop updated.",
            "schedule": ScheduleSerializer(schedule).data,
        }
    )


# ==========================
# 🔮 PREDICTION / FORECAST
# ==========================

def compute_future_load_for_schedule(schedule):
    """
    Core prediction function.

    Uses:
      - schedule.current_passengers
      - schedule.current_stop_sequence
      - Pre-informs for this (route, date) AFTER current stop

    Returns a dict that can be returned as JSON or used by admin demand views.
    """
    capacity = schedule.total_seats or (schedule.bus.capacity if schedule.bus else None)
    current_passengers = schedule.current_passengers or 0
    current_seq = schedule.current_stop_sequence or 0

    if capacity is None:
        capacity = 0

    route = schedule.route
    stops_qs = route.stops.all().order_by("sequence")

    # ---- Get all future pre-informs ----
    try:
        from preinforms.models import PreInform

        preinforms_qs = (
            PreInform.objects
            .filter(
                route=route,
                date_of_travel=schedule.date,
                boarding_stop__sequence__gt=current_seq,
            )
            .select_related("boarding_stop")
        )

        future_demand = {}
        for pi in preinforms_qs:
            seq = pi.boarding_stop.sequence
            incoming = getattr(pi, "passenger_count", None)
            if incoming is None:
                continue
            future_demand.setdefault(seq, 0)
            future_demand[seq] += incoming

    except Exception as e:
        print("⚠️ compute_future_load_for_schedule preinform error:", e)
        future_demand = {}

    # ---- Walk through future stops and accumulate ----
    running_load = current_passengers
    stops_output = []
    will_overflow = False
    overflow_from_stop_seq = None

    for stop in stops_qs:
        seq = stop.sequence

        if seq <= current_seq:
            continue

        incoming = future_demand.get(seq, 0)
        predicted_after = running_load + incoming
        overflow_here = predicted_after > capacity

        if overflow_here and not will_overflow:
            will_overflow = True
            overflow_from_stop_seq = seq

        stops_output.append(
            {
                "sequence": seq,
                "name": stop.name,
                "incoming_preinform": incoming,
                "predicted_after": predicted_after,
                "overflow": overflow_here,
            }
        )

        running_load = predicted_after

    return {
        "schedule_id": schedule.id,
        "route": {
            "id": route.id,
            "number": route.number,
            "name": route.name,
        },
        "capacity": capacity,
        "current_stop_sequence": current_seq,
        "current_passengers": current_passengers,
        "future_stops": stops_output,
        "will_overflow": will_overflow,
        "overflow_from_stop_sequence": overflow_from_stop_seq,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def schedule_forecast_view(request, schedule_id):
    """
    Get predicted load for a specific schedule,
    starting from its current_stop_sequence and current_passengers.

    GET /api/schedules/<schedule_id>/forecast/
    """
    user = request.user

    schedule = get_object_or_404(
        Schedule.objects.select_related("route", "bus", "driver"),
        id=schedule_id,
    )

    # Only this driver OR staff/superuser
    if schedule.driver_id != user.id and not (
        getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
    ):
        return Response(
            {"detail": "You are not allowed to view this schedule forecast."},
            status=status.HTTP_403_FORBIDDEN,
        )

    forecast = compute_future_load_for_schedule(schedule)
    return Response(forecast, status=status.HTTP_200_OK)
