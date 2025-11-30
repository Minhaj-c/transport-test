from django.shortcuts import render

# Create your views here.
"""
Schedules API Views
"""

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes,authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.shortcuts import render
from datetime import timedelta
import math
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
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
    if request.user.role != 'driver':
        return Response(
            {'error': 'Only drivers can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get driver's schedules for today and future
    today = timezone.now().date()
    schedules = Schedule.objects.filter(
        driver=request.user,
        date__gte=today
    ).select_related('route', 'bus').order_by('date', 'departure_time')
    
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
        return Response({
            'error': 'Invalid coordinates. Provide latitude, longitude, and optional radius.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get buses that are currently running (updated in last 5 minutes)
    five_minutes_ago = timezone.now() - timedelta(minutes=5)
    
    running_buses = Bus.objects.filter(
        is_running=True,
        current_latitude__isnull=False,
        current_longitude__isnull=False,
        last_location_update__gte=five_minutes_ago
    ).select_related('current_route', 'current_schedule')
    
    nearby_buses_list = []
    
    for bus in running_buses:
        distance = calculate_distance(
            user_lat, user_lng,
            float(bus.current_latitude), float(bus.current_longitude)
        )
        
        if distance <= radius_km:
            bus_data = LiveBusSerializer(bus).data
            bus_data['distance_km'] = round(distance, 2)
            nearby_buses_list.append(bus_data)
    
    # Sort by distance
    nearby_buses_list.sort(key=lambda x: x['distance_km'])
    
    return Response({
        'buses': nearby_buses_list,
        'user_location': {'latitude': user_lat, 'longitude': user_lng},
        'search_radius_km': radius_km,
        'total_found': len(nearby_buses_list)
    })


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
    print("Logged in user -> id:", user.id, "| email:", user.email, "| role:", getattr(user, "role", None))
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
        "| driver_email:", schedule.driver.email
    )

    # Only assigned driver or superuser can update
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

    from django.utils import timezone

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
        {
            "success": True,
            "message": "Bus location updated.",
        }
    )



@api_view(['GET'])
def bus_details(request, bus_id):
    """
    Get detailed information about a specific bus
    
    GET /api/buses/<bus_id>/
    """
    try:
        bus = Bus.objects.select_related('current_route', 'current_schedule').get(
            id=bus_id,
            is_running=True
        )
        return Response(LiveBusSerializer(bus).data)
    except Bus.DoesNotExist:
        return Response(
            {'error': 'Bus not found or not running'},
            status=status.HTTP_404_NOT_FOUND
        )


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two coordinates using Haversine formula
    Returns distance in kilometers
    """
    R = 6371  # Earth's radius in kilometers
    
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
    Serve the schedules frontend page
    """
    route_id = request.GET.get('route_id')
    context = {'route_id': route_id}
    return render(request, 'schedules.html', context)


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

    # Only this schedule's driver or superuser
    if schedule.driver_id != user.id and not user.is_superuser:
        print("❌ PERMISSION DENIED for user", user.id)
        return Response(
            {"detail": "Only the assigned driver can update passenger count."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # 👇 use your model helper (you said you have set_passenger_count)
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

    # Only that driver or admin can update
    if schedule.driver_id != user.id and not user.is_superuser:
        return Response(
            {"detail": "Only the assigned driver can update current stop."},
            status=status.HTTP_403_FORBIDDEN,
        )

    schedule.current_stop_sequence = stop_sequence
    schedule.save(update_fields=["current_stop_sequence"])

    # You can later hook your prediction logic here.

    return Response(
        {
            "success": True,
            "message": "Current stop updated.",
            "schedule": ScheduleSerializer(schedule).data,
        }
    )