"""
Schedules Serializers
Convert Bus and Schedule models to JSON
"""

from rest_framework import serializers
from .models import Bus, Schedule, BusSchedule
from routes.serializers import RouteSerializer
from routes.models import Stop



class BusSerializer(serializers.ModelSerializer):
    """
    Serializer for Bus model
    """
    class Meta:
        model = Bus
        fields = [
            'id',
            'number_plate',
            'capacity',
            'mileage',
            'service_type',
            'is_active'
        ]


class BusLocationSerializer(serializers.ModelSerializer):
    """
    Serializer for bus location tracking
    """
    class Meta:
        model = Bus
        fields = [
            'id',
            'number_plate',
            'current_latitude',
            'current_longitude',
            'last_location_update',
            'is_running',
            'current_route'
        ]


class LiveBusSerializer(serializers.ModelSerializer):
    """
    Serializer for live bus tracking with full details
    """
    route = RouteSerializer(source='current_route', read_only=True)
    schedule = serializers.SerializerMethodField()
    
    class Meta:
        model = Bus
        fields = [
            'id',
            'number_plate',
            'capacity',
            'current_latitude',
            'current_longitude',
            'last_location_update',
            'is_running',
            'route',
            'schedule'
        ]
    
    def get_schedule(self, obj):
        """Get current schedule details"""
        if obj.current_schedule:
            return {
                'id': obj.current_schedule.id,
                'available_seats': obj.current_schedule.available_seats,
                'total_seats': obj.current_schedule.total_seats,
                'departure_time': obj.current_schedule.departure_time,
                'arrival_time': obj.current_schedule.arrival_time,
                'date': obj.current_schedule.date,
                # 👇 optional, but useful if you want live count from bus side too
                'current_passengers': getattr(obj.current_schedule, "current_passengers", 0),
                'last_passenger_update': obj.current_schedule.last_passenger_update,
            }
        return None


class ScheduleSerializer(serializers.ModelSerializer):
    """
    Serializer for Schedule model
    Includes nested route and bus information
    """
    route = RouteSerializer(read_only=True)
    bus = BusSerializer(read_only=True)
    driver = serializers.SerializerMethodField()
    current_stop_sequence = serializers.IntegerField(read_only=True)
    current_stop_name = serializers.SerializerMethodField()
    next_stop_sequence = serializers.SerializerMethodField()
    next_stop_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Schedule
        fields = [
            'id',
            'route',
            'bus',
            'driver',
            'date',
            'departure_time',
            'arrival_time',
            'total_seats',
            'available_seats',
            'current_passengers',    
            'last_passenger_update', 
            'current_stop_sequence',  
            "current_stop_name",
            "next_stop_sequence",
            "next_stop_name",
            "is_spare_trip",
        ]
    
    def get_driver(self, obj):
        """Get driver information"""
        return {
            'id': obj.driver.id,
            'name': f"{obj.driver.first_name} {obj.driver.last_name}".strip() or obj.driver.email,
            'email': obj.driver.email
        }
    def _get_stops_for_route(self, obj):
        """
        Small helper: all stops for this route ordered by sequence.
        """
        if not obj.route_id:
            return Stop.objects.none()
        return obj.route.stops.all().order_by("sequence")

    def get_current_stop_name(self, obj):
        """
        Returns the current stop name based on current_stop_sequence.
        """
        seq = getattr(obj, "current_stop_sequence", None)
        if not seq:
            return None

        stop = self._get_stops_for_route(obj).filter(sequence=seq).first()
        return stop.name if stop else None

    def get_next_stop_sequence(self, obj):
        """
        Next stop sequence after current_stop_sequence (if any).
        """
        seq = getattr(obj, "current_stop_sequence", None)
        if not seq:
            return None

        qs = self._get_stops_for_route(obj).filter(sequence__gt=seq).order_by("sequence")
        next_stop = qs.first()
        return next_stop.sequence if next_stop else None

    def get_next_stop_name(self, obj):
        """
        Next stop name after current_stop_sequence (if any).
        """
        seq = getattr(obj, "current_stop_sequence", None)
        if not seq:
            return None

        qs = self._get_stops_for_route(obj).filter(sequence__gt=seq).order_by("sequence")
        next_stop = qs.first()
        return next_stop.name if next_stop else None    


class BusScheduleSerializer(serializers.ModelSerializer):
    """
    Serializer for BusSchedule (operational planning)
    """
    bus_details = BusSerializer(source='bus', read_only=True)
    route_details = RouteSerializer(source='route', read_only=True)
    
    class Meta:
        model = BusSchedule
        fields = [
            'id',
            'bus',
            'bus_details',
            'route',
            'route_details',
            'date',
            'start_time',
            'end_time'
        ]
