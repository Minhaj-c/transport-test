from django.shortcuts import render, get_object_or_404

"""
Schedules API Views
"""

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta,datetime,time,date
import math
from django.views.decorators.csrf import csrf_exempt

from .models import Schedule, Bus, Ticket
from routes.models import Stop
from .serializers import ScheduleSerializer, LiveBusSerializer, BusLocationSerializer
from routes.models import Route
from rest_framework.authentication import SessionAuthentication
from schedules.models import SpareBusSchedule, SpareDispatchRequest
from django.db.models import Q
from django.db import IntegrityError
from users.models import CustomUser
from django.db import transaction

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
        .exclude(status='completed')
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

    # 🔒 don't allow moving the bus backwards
    old_seq = schedule.current_stop_sequence or 0
    if stop_sequence < old_seq:
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
    Core prediction function with support for spare buses starting mid-route.

    Uses:
      - schedule.current_passengers
      - schedule.current_stop_sequence (for both regular buses and spare buses)
      - Pre-informs for this (route, date) with BOTH boarding & dropoff stops

    For spare buses (is_spare_trip=True):
      - Starts from current_stop_sequence (the overflow point)
      - Only considers boarding/alighting from that point onwards

    For each pre-inform:
      - passengers ride from boarding_seq up to (but NOT including) dropoff_seq.
    """

    capacity = schedule.total_seats or (
        schedule.bus.capacity if schedule.bus else None
    )
    current_passengers = schedule.current_passengers or 0
    current_seq = schedule.current_stop_sequence or 0
    
    print(f"=== compute_future_load DEBUG ===")
    print(f"schedule_id: {schedule.id}")
    print(f"current_seq: {current_seq}")
    print(f"current_passengers: {schedule.current_passengers}")
    try:
        _debug_tickets = Ticket.objects.filter(schedule=schedule).select_related('boarding_stop', 'dropoff_stop')
        print(f"total tickets: {_debug_tickets.count()}")
        for _t in _debug_tickets:
            print(f"  ticket id={_t.id} | boarding_seq={_t.boarding_stop.sequence} | dropoff_seq={_t.dropoff_stop.sequence} | count={_t.passenger_count}")
        print(f"board_map will be built from above tickets")
    except Exception as _e:
        print(f"debug error: {_e}")
    print(f"=================================")
    # ===== END DEBUG =====

    if capacity is None:
        capacity = 0

    route = schedule.route
    
    # 🔥 For spare buses, only show stops from their starting point onwards
    if getattr(schedule, 'is_spare_trip', False) and current_seq > 0:
        stops_qs = route.stops.filter(sequence__gte=current_seq).order_by("sequence")
    else:
        # Regular bus: show all stops after current position
        stops_qs = route.stops.filter(sequence__gt=current_seq).order_by("sequence")

    # ---- Get all relevant pre-informs ----
    try:
        from preinforms.models import PreInform

        preinforms_qs = (
            PreInform.objects
            .filter(route=route, date_of_travel=schedule.date, status="noted")
            .select_related("boarding_stop", "dropoff_stop")
        )

        board_map = {}
        drop_map = {}

        for pi in preinforms_qs:
            count = getattr(pi, "passenger_count", 0) or 0
            if count <= 0:
                continue

            b_seq = pi.boarding_stop.sequence
            d_stop = getattr(pi, "dropoff_stop", None)
            d_seq = d_stop.sequence if d_stop else None

            # people boarding after our current position
            if b_seq > current_seq:
                board_map[b_seq] = board_map.get(b_seq, 0) + count

            # drop-offs that happen after current position
            if d_seq is not None and d_seq > current_seq:
                drop_map[d_seq] = drop_map.get(d_seq, 0) + count

    except Exception as e:
        print("⚠️ compute_future_load_for_schedule preinform error:", e)
        board_map = {}
        drop_map = {}
    try:
        tickets_qs = Ticket.objects.filter(
            schedule=schedule
        ).select_related('boarding_stop', 'dropoff_stop')

        for ticket in tickets_qs:
            b_seq = ticket.boarding_stop.sequence
            d_seq = ticket.dropoff_stop.sequence
            count = ticket.passenger_count

            # Future boarding — passenger not yet on bus
            if b_seq > current_seq:
                board_map[b_seq] = board_map.get(b_seq, 0) + count

            # Dropoff ahead — covers both:
            # 1. Already on bus (boarded at or before current stop)
            # 2. Will board at a future stop
            if d_seq > current_seq:
                drop_map[d_seq] = drop_map.get(d_seq, 0) + count

    except Exception as e:
        print("compute_future_load ticket error:", e)
    # 🔥 For spare buses starting mid-route, begin with 0 passengers
    if getattr(schedule, 'is_spare_trip', False):
        running_load = 0  # Spare bus starts empty
        current_passengers = 0  # Override display value
    else:
        running_load = current_passengers
        
    stops_output = []
    will_overflow = False
    overflow_from_stop_seq = None

    for stop in stops_qs:
        seq = stop.sequence

        incoming = board_map.get(seq, 0)
        leaving = drop_map.get(seq, 0)

        running_load = max(running_load + incoming - leaving, 0)
        overflow_here = capacity and running_load > capacity

        if overflow_here and not will_overflow:
            will_overflow = True
            overflow_from_stop_seq = seq

        stops_output.append(
            {
                "sequence": seq,
                "name": stop.name,
                "incoming_preinform": incoming,
                "alighting_preinform": leaving,
                "predicted_after": running_load,
                "overflow": overflow_here,
            }
        )

    return {
        "schedule_id": schedule.id,
        "route": {
            "id": route.id,
            "number": route.number,
            "name": route.name,
        },
        "capacity": capacity,
        "current_stop_sequence": current_seq,
        "start_stop_sequence": getattr(schedule, 'starting_stop_sequence', 0) or 0,
        "end_stop_sequence": stops_output[-1]["sequence"] if stops_output else None,
        "current_passengers": current_passengers,
        "is_spare_trip": getattr(schedule, 'is_spare_trip', False),
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


# ==========================
#  SPARE BUS APIs
# ==========================

@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
def enter_spare_mode(request):
    """
    Driver enters spare mode (activates their spare window).
    POST /api/schedules/spare/enter/
    """
    user = request.user
    
    if not user.is_authenticated:
        return Response(
            {'error': 'Authentication required'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    today = timezone.now().date()
    now = timezone.now()

    # Find driver's bus from today's schedule
    today_schedule = Schedule.objects.filter(
        driver=user,
        date=today
    ).select_related('bus').first()

    if not today_schedule:
        return Response(
            {'error': 'No bus assigned to you today.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    bus = today_schedule.bus

    # Find spare schedule for THIS SPECIFIC bus
    spare = SpareBusSchedule.objects.filter(
        bus=bus,
        date=today,
        status='waiting'
    ).first()

    if not spare:
        return Response(
            {'error': 'You do not have a spare schedule assigned today.'},
            status=status.HTTP_404_NOT_FOUND
        )

    spare.status = 'active'
    spare.activated_at = now
    spare.save()

    remaining_minutes = spare.remaining_minutes

    return Response({
        'success': True,
        'message': 'Spare mode activated',
        'spare_start_time': str(spare.spare_start_time),
        'spare_end_time': str(spare.spare_end_time),
        'remaining_minutes': remaining_minutes,
    })
    
    
@api_view(['GET'])
@authentication_classes([CsrfExemptSessionAuthentication])
def get_spare_status(request):
    """
    Get spare status for driver.
    GET /api/schedules/spare/status/
    """
    user = request.user
    today = timezone.now().date()

    if not user.is_authenticated:
        return Response({
            'has_spare': False, 
            'message': 'Not logged in'
        })

    today_schedule = Schedule.objects.filter(
        driver=user,
        date=today
    ).select_related('bus').first()

    if not today_schedule:
        return Response({
            'has_spare': False, 
            'message': 'No schedule today'
        })

    spare = SpareBusSchedule.objects.filter(
        bus=today_schedule.bus,
        date=today
    ).first()

    if not spare:
        return Response({'has_spare': False})

    return Response({
        'has_spare': True,
        'spare_id': spare.id,
        'spare_start': str(spare.spare_start_time),
        'spare_end': str(spare.spare_end_time),
        'status': spare.status,
        'remaining_minutes': spare.remaining_minutes,
        'is_active': spare.status == 'active',
        'is_dispatched': spare.status == 'dispatched',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([CsrfExemptSessionAuthentication])
def request_spare_bus(request):
    """
    Request spare bus for a schedule.
    POST /api/schedules/spare/request/
    Body: {"schedule_id": 12, "reason": "Bus breakdown"}
    """
    schedule_id = request.data.get('schedule_id')
    reason = request.data.get('reason', 'Spare bus requested')

    if not schedule_id:
        return Response({'error': 'schedule_id required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        original_schedule = Schedule.objects.select_related('route', 'bus', 'driver').get(id=schedule_id)
    except Schedule.DoesNotExist:
        return Response({'error': 'Schedule not found'}, status=status.HTTP_404_NOT_FOUND)

    today = timezone.now().date()
    now = timezone.now()

    available_spares = SpareBusSchedule.objects.filter(
        date=today,
        status='active',
        spare_end_time__gt=now.time()
    ).select_related('bus').order_by('spare_end_time')

    if not available_spares.exists():
        SpareDispatchRequest.objects.create(
            original_schedule=original_schedule,
            status='failed',
            reason=f'{reason} - No spare buses available'
        )
        return Response(
            {'error': 'No spare buses available. Drivers must click "Enter Spare Mode" first.'},
            status=status.HTTP_404_NOT_FOUND
        )

    best_spare = None
    best_remaining = -1
    for spare in available_spares:
        remaining = spare.remaining_minutes
        if remaining > best_remaining:
            best_remaining = remaining
            best_spare = spare

    if best_spare is None or best_remaining < 10:
        return Response(
            {'error': 'No spare bus has enough time (min 10 minutes needed).'},
            status=status.HTTP_400_BAD_REQUEST
        )

    spare_driver = None
    
    if hasattr(best_spare.bus, 'assigned_driver') and best_spare.bus.assigned_driver:
        spare_driver = best_spare.bus.assigned_driver
    
    if not spare_driver:
        today_schedule = Schedule.objects.filter(
            bus=best_spare.bus,
            date=today
        ).select_related('driver').first()
        
        if today_schedule:
            spare_driver = today_schedule.driver
    
    if not spare_driver:
        spare_driver = original_schedule.driver

    spare_schedule = Schedule.objects.create(
        bus=best_spare.bus,
        route=original_schedule.route,
        driver=spare_driver,
        date=today,
        departure_time=original_schedule.departure_time,
        arrival_time=original_schedule.arrival_time,
        total_seats=best_spare.bus.capacity,
        available_seats=best_spare.bus.capacity,
        is_spare_trip=True,
    )

    best_spare.status = 'dispatched'
    best_spare.dispatched_to_schedule = spare_schedule
    best_spare.dispatched_at = now
    best_spare.save()

    SpareDispatchRequest.objects.create(
        original_schedule=original_schedule,
        assigned_spare=best_spare,
        status='assigned',
        reason=reason,
        assigned_at=now,
    )

    return Response({
        'success': True,
        'message': f'Spare bus {best_spare.bus.number_plate} assigned!',
        'spare_bus': best_spare.bus.number_plate,
        'driver': spare_driver.get_full_name() if spare_driver else 'Unknown',
        'remaining_minutes': best_remaining,
        'spare_schedule_id': spare_schedule.id,
        'route': original_schedule.route.number,
        'departure_time': str(original_schedule.departure_time),
    })


@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
def report_delayed_arrival(request):
    """
    Driver reports they will be late returning from spare duty.
    POST /api/schedules/spare/delayed/
    """
    user = request.user
    
    if not user.is_authenticated:
        return Response(
            {'error': 'Authentication required'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    schedule_id = request.data.get('schedule_id')
    estimated_arrival = request.data.get('estimated_arrival')  # "HH:MM"
    
    if not schedule_id or not estimated_arrival:
        return Response(
            {'error': 'schedule_id and estimated_arrival required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        current_schedule = Schedule.objects.select_related('bus', 'driver', 'route').get(id=schedule_id)
    except Schedule.DoesNotExist:
        return Response(
            {'error': 'Schedule not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    try:
        arrival_time = datetime.strptime(estimated_arrival, '%H:%M').time()
    except ValueError:
        return Response(
            {'error': 'Invalid time format. Use HH:MM'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    now = timezone.now()
    today = now.date()
    
    next_schedule = Schedule.objects.filter(
        bus=current_schedule.bus,
        date=today,
        departure_time__gt=current_schedule.departure_time,
        is_spare_trip=False
    ).order_by('departure_time').first()
    
    if not next_schedule:
        return Response({
            'can_make_it': True,
            'message': f'✅ No trips scheduled after this spare duty.',
        })
    
    arrival_datetime = datetime.combine(today, arrival_time)
    next_trip_datetime = datetime.combine(today, next_schedule.departure_time)
    time_diff = (arrival_datetime - next_trip_datetime).total_seconds() / 60
    
    print(f"🔍 Time check: Arrive {arrival_time} vs Next trip {next_schedule.departure_time} = {time_diff:.1f} min")
    
    if time_diff <= 0:
        print(f"✅ Driver is ON TIME (early by {abs(time_diff):.1f} min)")
        return Response({
            'can_make_it': True,
            'message': f'✅ You will arrive at {estimated_arrival}, in time for {next_schedule.departure_time.strftime("%H:%M")} trip.',
        })
    
    minutes_late = int(time_diff)
    print(f"❌ Driver late by {minutes_late} minutes - finding spare...")
    
    available_spares = SpareBusSchedule.objects.filter(
        date=today,
        status='active',
        spare_end_time__gt=now.time()
    ).select_related('bus').exclude(
        bus=current_schedule.bus
    ).order_by('-spare_end_time')
    
    best_spare = None
    for spare in available_spares:
        if spare.remaining_minutes >= 15:
            best_spare = spare
            break
    
    if not best_spare:
        return Response({
            'can_make_it': False,
            'success': False,
            'message': f'⚠️ No spare buses available to cover {next_schedule.departure_time.strftime("%H:%M")} trip.',
            'minutes_late': minutes_late,
        })
    
    print(f"✅ Found spare: {best_spare.bus.number_plate} ({best_spare.remaining_minutes} min)")
    
    spare_bus_driver = CustomUser.objects.filter(
        role='driver'
    ).exclude(id=user.id).first()
    
    if not spare_bus_driver:
        spare_bus_driver = user
    
    existing_backup = Schedule.objects.filter(
        driver=spare_bus_driver,
        date=today,
        departure_time=next_schedule.departure_time
    ).first()
    
    if existing_backup:
        print(f"⚠️ Backup already assigned (ID: {existing_backup.id})")
        return Response({
            'can_make_it': False,
            'success': True,
            'spare_bus_assigned': True,
            'message': f"⚡ Spare bus {best_spare.bus.number_plate} already assigned to cover {next_schedule.departure_time.strftime('%H:%M')} trip.",
            'backup_bus': best_spare.bus.number_plate,
        })
    
    try:
        backup_schedule = Schedule.objects.create(
            bus=best_spare.bus,
            route=next_schedule.route,
            driver=spare_bus_driver,
            date=today,
            departure_time=next_schedule.departure_time,
            arrival_time=next_schedule.arrival_time,
            total_seats=best_spare.bus.capacity,
            available_seats=best_spare.bus.capacity,
            is_spare_trip=True,
        )
        print(f"✅ Created backup schedule ID: {backup_schedule.id}")
    except IntegrityError as e:
        print(f"❌ IntegrityError creating backup: {e}")
        return Response({
            'success': False,
            'error': f'Schedule already exists for this time slot.',
        }, status=400)
    
    best_spare.status = 'dispatched'
    best_spare.dispatched_to_schedule = backup_schedule
    best_spare.dispatched_at = now
    best_spare.save()
    
    next_schedule.status = 'covered_by_spare'
    next_schedule.save()
    
    handoff_message = ""
    
    backup_bus_next_trip = Schedule.objects.filter(
        bus=best_spare.bus,
        date=today,
        departure_time__gt=arrival_time,
        is_spare_trip=False
    ).exclude(
        id=backup_schedule.id
    ).order_by('departure_time').first()
    
    if backup_bus_next_trip:
        existing_handoff = Schedule.objects.filter(
            driver=user,
            date=today,
            departure_time=backup_bus_next_trip.departure_time,
            is_spare_trip=True
        ).first()
        
        if not existing_handoff:
            try:
                handoff_schedule = Schedule.objects.create(
                    bus=current_schedule.bus,
                    route=backup_bus_next_trip.route,
                    driver=user,
                    date=today,
                    departure_time=backup_bus_next_trip.departure_time,
                    arrival_time=backup_bus_next_trip.arrival_time,
                    total_seats=current_schedule.bus.capacity,
                    available_seats=current_schedule.bus.capacity,
                    is_spare_trip=True,
                )
                
                backup_bus_next_trip.status = 'covered_by_spare'
                backup_bus_next_trip.save()
                
                handoff_message = (
                    f"\n🔄 When you return at {estimated_arrival}, you will cover "
                    f"{best_spare.bus.number_plate}'s {backup_bus_next_trip.departure_time.strftime('%H:%M')} trip on Route {backup_bus_next_trip.route.number}."
                )
                print(f"✅ Created handoff schedule ID: {handoff_schedule.id}")
            except IntegrityError as e:
                print(f"⚠️ Handoff conflict: {e}")
                handoff_message = ""
    
    return Response({
        'can_make_it': False,
        'success': True,
        'spare_bus_assigned': True,
        'message': (
            f"⚡ Spare bus {best_spare.bus.number_plate} will cover your "
            f"{next_schedule.departure_time.strftime('%H:%M')} trip on Route {next_schedule.route.number}."
            f"{handoff_message}"
        ),
        'backup_bus': best_spare.bus.number_plate,
        'covered_trip_time': next_schedule.departure_time.strftime('%H:%M'),
        'your_arrival': estimated_arrival,
        'minutes_late': minutes_late,
    })

        
@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
def exit_spare_mode(request):
    """
    Driver exits spare mode.
    POST /api/schedules/spare/exit/
    """
    user = request.user
    
    if not user.is_authenticated:
        return Response(
            {'error': 'Authentication required'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    today = timezone.now().date()

    today_schedule = Schedule.objects.filter(
        driver=user,
        date=today
    ).select_related('bus').first()

    if not today_schedule:
        return Response(
            {'error': 'No bus assigned to you today.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    bus = today_schedule.bus

    spare = SpareBusSchedule.objects.filter(
        bus=bus,
        date=today,
        status='active'
    ).first()

    if not spare:
        return Response(
            {'error': 'You are not in spare mode.'},
            status=status.HTTP_404_NOT_FOUND
        )

    spare.status = 'completed'
    spare.save()

    return Response({
        'success': True,
        'message': 'Spare mode deactivated',
    })
    
    
@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
def complete_spare_trip(request):
    """
    Driver completes spare trip and system automatically assigns handoff trip if exists.
    POST /api/schedules/spare/complete/
    Body: {"schedule_id": 123}
    """
    user = request.user
    
    if not user.is_authenticated:
        return Response({'error': 'Authentication required'}, status=401)
    
    schedule_id = request.data.get('schedule_id')
    
    try:
        schedule = Schedule.objects.select_related('bus', 'driver').get(id=schedule_id)
    except Schedule.DoesNotExist:
        return Response({'error': 'Schedule not found'}, status=404)
    
    if not schedule.is_spare_trip:
        return Response({'error': 'Not a spare trip'}, status=400)
    
    if schedule.driver.id != user.id:
        return Response({'error': 'Not your schedule'}, status=403)
    
    today = timezone.now().date()
    now_time = timezone.now().time()
    
    handoff_schedule = Schedule.objects.filter(
        bus=schedule.bus,
        driver=user,
        date=today,
        is_spare_trip=True,
        departure_time__gte=now_time
    ).exclude(id=schedule_id).order_by('departure_time').first()
    
    if handoff_schedule:
        return Response({
            'success': True,
            'has_handoff': True,
            'message': (
                f"✅ Spare trip completed! "
                f"🔄 You have a handoff assignment: "
                f"Route {handoff_schedule.route.number} at {handoff_schedule.departure_time}"
            ),
            'handoff_schedule': {
                'id': handoff_schedule.id,
                'route_number': handoff_schedule.route.number,
                'route_name': handoff_schedule.route.name,
                'departure_time': str(handoff_schedule.departure_time),
                'arrival_time': str(handoff_schedule.arrival_time),
            }
        })
    
    return Response({
        'success': True,
        'has_handoff': False,
        'message': '✅ Spare trip completed! No additional assignments.',
    })


# ==========================
#  TICKET APIs
# ==========================

@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])  # ✅ FIXES mobile session auth
@permission_classes([IsAuthenticated])
def issue_ticket(request):
    """
    Conductor issues a ticket when passengers board.

    POST /api/schedules/issue-ticket/
    {
        "schedule_id": 10,
        "boarding_stop_id": 3,
        "dropoff_stop_id": 7,
        "passenger_count": 5
    }
    """
    schedule_id     = request.data.get('schedule_id')
    boarding_id     = request.data.get('boarding_stop_id')
    dropoff_id      = request.data.get('dropoff_stop_id')
    passenger_count = int(request.data.get('passenger_count', 1))

    if not all([schedule_id, boarding_id, dropoff_id]):
        return Response(
            {'error': 'schedule_id, boarding_stop_id and dropoff_stop_id are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if passenger_count < 1:
        return Response(
            {'error': 'passenger_count must be at least 1.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        schedule = Schedule.objects.select_related('route', 'bus').get(id=schedule_id)
    except Schedule.DoesNotExist:
        return Response(
            {'error': 'Schedule not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # ✅ Compare by ID + superuser bypass
    if schedule.driver_id != request.user.id and not request.user.is_superuser:
        return Response(
            {'error': 'Only the assigned driver can issue tickets for this schedule.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        boarding_stop = Stop.objects.get(id=boarding_id, route=schedule.route)
    except Stop.DoesNotExist:
        return Response(
            {'error': 'Boarding stop not found on this route.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        dropoff_stop = Stop.objects.get(id=dropoff_id, route=schedule.route)
    except Stop.DoesNotExist:
        return Response(
            {'error': 'Dropoff stop not found on this route.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if boarding_stop.sequence >= dropoff_stop.sequence:
        return Response(
            {'error': 'Dropoff stop must be after boarding stop.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    current_seq = schedule.current_stop_sequence or 0
    if dropoff_stop.sequence < current_seq:
        return Response(
            {'error' : f'DropOff dtop "{dropoff_stop.name}" is already passed. Bus is currently at stop {current_seq}'},
            status=status.HTTP_400_BAD_REQUEST,
        )    

    with transaction.atomic():
        Ticket.objects.create(
            schedule=schedule,
            boarding_stop=boarding_stop,
            dropoff_stop=dropoff_stop,
            passenger_count=passenger_count,
        )
        # ✅ Use set_passenger_count to keep current_passengers + available_seats in sync
        new_count = (schedule.current_passengers or 0) + passenger_count
        schedule.set_passenger_count(new_count)

    return Response({
        'success': True,
        'message': f'Ticket issued for {passenger_count} passenger(s).',
        'ticket': {
            'boarding_stop':   boarding_stop.name,
            'dropoff_stop':    dropoff_stop.name,
            'passenger_count': passenger_count,
        },
        'schedule': {
            'id':                 schedule.id,
            'current_passengers': schedule.current_passengers,
            'total_seats':        schedule.total_seats,
            'available_seats':    schedule.available_seats,
        }
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def arrived_at_stop(request):
    """
    Driver marks bus as arrived at a stop.
    Auto-decrements passengers whose dropoff is this stop.

    POST /api/schedules/arrived-at-stop/
    {
        "schedule_id": 10,
        "stop_id": 7
    }
    """
    schedule_id = request.data.get('schedule_id')
    stop_id     = request.data.get('stop_id')

    if not all([schedule_id, stop_id]):
        return Response(
            {'error': 'schedule_id and stop_id are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        schedule = Schedule.objects.select_related('route').get(id=schedule_id)
    except Schedule.DoesNotExist:
        return Response(
            {'error': 'Schedule not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if schedule.driver_id != request.user.id and not request.user.is_superuser:
        return Response(
            {'error': 'Only the assigned driver can update stop.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        stop = Stop.objects.get(id=stop_id, route=schedule.route)
    except Stop.DoesNotExist:
        return Response(
            {'error': 'Stop not found on this route.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ✅ BACKWARD GUARD — same as updateCurrentStop
    old_seq = schedule.current_stop_sequence or 0
    if stop.sequence < old_seq:
        return Response(
            {
                'success': False,
                'message': (
                    f'Ignored: stop sequence {stop.sequence} '
                    f'is less than current {old_seq}.'
                ),
                'current_stop_sequence': old_seq,
            },
            status=status.HTTP_200_OK,
        )

    all_stops       = list(schedule.route.stops.order_by('sequence'))
    is_last_stop    = stop.sequence == all_stops[-1].sequence
    alighting_count = 0
    
    

    with transaction.atomic():
        schedule.current_stop_sequence = stop.sequence
        schedule.save(update_fields=['current_stop_sequence'])

        # Auto-decrement passengers alighting at this stop
        alighting_tickets = Ticket.objects.filter(
            schedule=schedule,
            dropoff_stop__sequence=stop.sequence,
        )
        alighting_count = sum(t.passenger_count for t in alighting_tickets)

        if alighting_count > 0:
            new_count = max(0, (schedule.current_passengers or 0) - alighting_count)
            schedule.set_passenger_count(new_count)

        # Reset everything at last stop
        if is_last_stop:
            schedule.set_passenger_count(0)
            schedule.current_stop_sequence = 0
            schedule.status = 'completed'
            schedule.save(update_fields=['current_stop_sequence','status'])

    return Response({
        'success':            True,
        'stop': {
            'id':       stop.id,
            'name':     stop.name,
            'sequence': stop.sequence,
        },
        'alighted':           alighting_count,
        'current_passengers': schedule.current_passengers,
        'available_seats':    schedule.available_seats,
        'is_last_stop':       is_last_stop,
        'route_complete':     is_last_stop,
    })