"""
Route and Stop Models
Defines bus routes and their stops
"""

from django.db import models
from zones.models import Zone   # ✅ NEW: link routes to zones


class Route(models.Model):
    """
    Bus Route Model
    Represents a complete bus route from origin to destination
    """
    # Basic information
    number = models.CharField(
        max_length=10,
        unique=True,
        help_text="Route number (e.g., 101, 102)"
    )
    name = models.CharField(
        max_length=100,
        help_text="Route name (e.g., Downtown Express)"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional route description"
    )

    # Route details
    origin = models.CharField(
        max_length=100,
        help_text="Starting point"
    )
    destination = models.CharField(
        max_length=100,
        help_text="Ending point"
    )
    total_distance = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Total distance in kilometers"
    )
    duration = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=1.0,
        help_text="Duration of trip in hours (e.g., 1.5 for 1 hour 30 minutes)"
    )

    # Operational timings
    turnaround_time = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=0.33,
        help_text="Turnaround time at terminal in hours (e.g., 0.33 for 20 minutes)"
    )
    buffer_time = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=0.16,
        help_text="Buffer time for delays in hours (e.g., 0.16 for 10 minutes)"
    )

    # ✅ NEW: which zone owns this route
    zone = models.ForeignKey(
        Zone,
        on_delete=models.CASCADE,
        related_name="routes",
        null=True,
        blank=True,
        help_text="Operational zone that manages this route"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Route'
        verbose_name_plural = 'Routes'
        ordering = ['number']

    def __str__(self):
        # Show zone too (useful for admins)
        if self.zone:
            return f"{self.number}: {self.origin} → {self.destination} ({self.zone.name})"
        return f"{self.number}: {self.origin} → {self.destination}"

    def calculate_trips_per_day(self, operational_hours=15):
        """
        Calculate how many round trips a bus can make on this route in a day.

        Args:
            operational_hours: Total hours of operation (default 15: 6 AM to 9 PM)

        Returns:
            int: Number of possible round trips
        """
        # Total time for one round trip
        total_time_per_trip = (self.duration * 2) + self.turnaround_time + self.buffer_time

        # Calculate trips
        trips = operational_hours / float(total_time_per_trip)

        return int(trips)


class Stop(models.Model):
    """
    Bus Stop Model
    Represents individual stops along a route
    """
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name='stops',
        help_text="Route this stop belongs to"
    )
    name = models.CharField(
        max_length=100,
        help_text="Stop name (e.g., Central Library, Maple St & 5th Ave)"
    )
    sequence = models.PositiveIntegerField(
        help_text="Order of stop on the route (1, 2, 3...)"
    )
    distance_from_origin = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Distance from route start in kilometers"
    )
    is_limited_stop = models.BooleanField(
        default=False,
        help_text="Whether this is a major stop served by limited stop buses"
    )

    class Meta:
        verbose_name = 'Stop'
        verbose_name_plural = 'Stops'
        ordering = ['route', 'sequence']
        unique_together = [
            ['route', 'sequence'],  # Ensure unique sequence per route
            ['route', 'name'],      # Ensure unique stop name per route
        ]

    def __str__(self):
        return f"{self.sequence}. {self.name} (Route {self.route.number})"
