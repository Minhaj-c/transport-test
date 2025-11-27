"""
Routes Admin Configuration
"""

from django.contrib import admin
from .models import Route, Stop


class StopInline(admin.TabularInline):
    """
    Inline admin for stops inside route admin
    """
    model = Stop
    extra = 1
    fields = ('sequence', 'name', 'distance_from_origin', 'is_limited_stop')
    ordering = ('sequence',)


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    """
    Admin configuration for Route model
    """

    list_display = (
        'number',
        'name',
        'origin',
        'destination',
        'total_distance',
        'duration',
        'zone',              # ✅ NEW
        'stop_count'
    )

    list_filter = ('zone', 'origin', 'destination', 'created_at')  # ✅ NEW zone filter
    search_fields = ('number', 'name', 'origin', 'destination')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Basic Information', {
            'fields': ('number', 'name', 'description')
        }),

        ('Route Details', {
            'fields': ('origin', 'destination', 'total_distance', 'duration')
        }),

        ('Zone Assignment', {           # ✅ NEW FIELDSET
            'fields': ('zone',)
        }),

        ('Operational Settings', {
            'fields': ('turnaround_time', 'buffer_time')
        }),

        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [StopInline]

    def stop_count(self, obj):
        """Display number of stops"""
        return obj.stops.count()
    stop_count.short_description = 'Stops'


@admin.register(Stop)
class StopAdmin(admin.ModelAdmin):
    """
    Admin configuration for Stop model
    """

    list_display = (
        'name',
        'route',
        'sequence',
        'distance_from_origin',
        'is_limited_stop'
    )

    list_filter = ('route', 'is_limited_stop')
    search_fields = ('name', 'route__number', 'route__name')
    ordering = ('route', 'sequence')

    fieldsets = (
        ('Basic Info', {
            'fields': ('route', 'name', 'sequence')
        }),
        ('Location Details', {
            'fields': ('distance_from_origin', 'is_limited_stop')
        }),
    )
