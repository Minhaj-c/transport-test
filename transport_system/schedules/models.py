"""
Bus and Schedule Models
Manages buses and their schedules
"""

from django.db import models
from django.conf import settings
from routes.models import Route


class Bus(models.Model):
    """
    Bus Model
    Represents physical buses in the fleet
    """
    # Basic information
    number_plate = models.CharField(
        max_length=15,
        unique=True,
        help_text="Vehicle registration number (e.g., KL-01-AB-1234)"
    )
    capacity = models.PositiveIntegerField(
        default=40,
        help_text="Total number of seats"
    )
    mileage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5.0,
        help_text="Fuel efficiency in km/liter"
    )
    
    # Service type
    SERVICE_TYPES = (
        ('all_stop', 'All Stop Service'),
        ('limited_stop', 'Limited Stop Service'),
        ('express', 'Express Service'),
    )
    service_type = models.CharField(
        max_length=20,
        choices=SERVICE_TYPES,
        default='all_stop',
        help_text="Type of service this bus provides"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether bus is operational"
    )
    
    # Real-time tracking fields
    current_latitude = models.DecimalField(
        max_digits=10,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Current GPS latitude"
    )
    current_longitude = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Current GPS longitude"
    )
    last_location_update = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When location was last updated"
    )
    is_running = models.BooleanField(
        default=False,
        help_text="Is bus currently on route"
    )
    current_route = models.ForeignKey(
        Route,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Route currently being served"
    )
    current_schedule = models.ForeignKey(
        'Schedule',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='current_buses',
        help_text="Current active schedule"
    )
    
    class Meta:
        verbose_name = 'Bus'
        verbose_name_plural = 'Buses'
        ordering = ['number_plate']
    
    def __str__(self):
        return f"{self.number_plate} (Seats: {self.capacity})"
    
    def update_location(self, latitude, longitude):
        """
        Update bus location with timestamp
        """
        from django.utils import timezone
        self.current_latitude = latitude
        self.current_longitude = longitude
        self.last_location_update = timezone.now()
        self.save(update_fields=['current_latitude', 'current_longitude', 'last_location_update'])


class Schedule(models.Model):
    """
    Bus Schedule Model
    Represents a specific bus trip on a route
    """
    # Relationships
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name='schedules',
        help_text="Route for this schedule"
    )
    bus = models.ForeignKey(
        Bus,
        on_delete=models.CASCADE,
        related_name='schedules',
        help_text="Bus assigned to this schedule"
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'driver'},
        related_name='schedules',
        help_text="Driver assigned to this schedule"
    )
    
    # Timing
    date = models.DateField(help_text="Date of the trip")
    departure_time = models.TimeField(help_text="Start time from origin")
    arrival_time = models.TimeField(help_text="Approximate arrival at destination")
    
    # Seat management
    total_seats = models.PositiveIntegerField(
        help_text="Total available seats (usually equals bus capacity)"
    )
    available_seats = models.PositiveIntegerField(
        help_text="Currently available seats"
    )
    current_passengers = models.PositiveIntegerField(
        default=0,
        help_text="Live passenger count reported by driver app"
    )
    last_passenger_update = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When driver last updated passenger count"
    )
    
    current_stop_sequence = models.PositiveIntegerField(
        default=0,
        blank=True,
        help_text="Sequence number of the current stop in the route",
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Schedule'
        verbose_name_plural = 'Schedules'
        ordering = ['date', 'departure_time']
        # Prevent double-booking
        unique_together = [
            ['bus', 'date', 'departure_time'],
            ['driver', 'date', 'departure_time'],
        ]
    
    def __str__(self):
        return f"{self.route.number} - {self.date} {self.departure_time} ({self.bus.number_plate})"
    
    def is_seat_available(self):
        """Check if seats are available"""
        return self.available_seats > 0
    
    def book_seat(self, count=1):
        """
        Book seats on this schedule
        
        Args:
            count: Number of seats to book
        
        Returns:
            bool: True if booking successful, False otherwise
        """
        if self.available_seats >= count:
            self.available_seats -= count
            self.save()
            return True
        return False
    
    def set_passenger_count(self, count: int):
        """
        Update current passenger count and keep available seats in sync.
        """
        from django.utils import timezone

        safe_count = max(0, int(count))
        self.current_passengers = safe_count
        self.last_passenger_update = timezone.now()

        # If you are using total_seats / available_seats, keep it updated
        if hasattr(self, "total_seats") and self.total_seats is not None:
            self.available_seats = max(0, self.total_seats - safe_count)

        self.save(
            update_fields=[
                "current_passengers",
                "last_passenger_update",
                "available_seats",
            ]
        )
        
        


class BusSchedule(models.Model):
    """
    Bus Assignment Model
    Tracks which bus is assigned to which route for operational planning
    """
    bus = models.ForeignKey(
        Bus,
        on_delete=models.CASCADE,
        related_name='bus_schedules',
        help_text="Bus being assigned"
    )
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name='bus_schedules',
        help_text="Route being served"
    )
    date = models.DateField(help_text="Date of assignment")
    start_time = models.TimeField(help_text="When bus starts this route")
    end_time = models.TimeField(help_text="When bus finishes this route")
    
    class Meta:
        verbose_name = 'Bus Assignment'
        verbose_name_plural = 'Bus Assignments'
        ordering = ['date', 'start_time']
    
    def __str__(self):
        return f"{self.bus} on {self.route} - {self.date} {self.start_time}-{self.end_time}"
    
    def duration_hours(self):
        """Calculate duration of this assignment in hours"""
        from datetime import datetime
        start = datetime.combine(self.date, self.start_time)
        end = datetime.combine(self.date, self.end_time)
        duration = (end - start).total_seconds() / 3600
        return round(duration, 1)