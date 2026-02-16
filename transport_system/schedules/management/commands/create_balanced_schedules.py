# schedules/management/commands/create_balanced_schedules.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, time, timedelta
import random
from decimal import Decimal

from schedules.models import Bus, Schedule, SpareBusSchedule
from routes.models import Route
from users.models import CustomUser


class Command(BaseCommand):
    help = 'Create balanced weekly schedules (2-3 trips per route per bus per day)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--week-start',
            type=str,
            help='Week start date (YYYY-MM-DD). Default: next Monday'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing schedules for this week before generating'
        )

    def handle(self, *args, **options):
        # Determine week start
        if options['week_start']:
            week_start = date.fromisoformat(options['week_start'])
        else:
            today = timezone.now().date()
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            week_start = today + timedelta(days=days_until_monday)
        
        week_end = week_start + timedelta(days=6)
        
        self.stdout.write(f"\n🎯 Creating BALANCED Weekly Schedules")
        self.stdout.write(f"📅 Week: {week_start} to {week_end}")
        self.stdout.write(f"📋 Pattern: 2-3 trips per route per bus per day\n")
        
        # Check existing schedules
        existing = Schedule.objects.filter(date__gte=week_start, date__lte=week_end).count()
        if existing > 0:
            if options['clear_existing']:
                self.stdout.write(self.style.WARNING(f"⚠️  Deleting {existing} existing schedules..."))
                Schedule.objects.filter(date__gte=week_start, date__lte=week_end).delete()
                SpareBusSchedule.objects.filter(date__gte=week_start, date__lte=week_end).delete()
                self.stdout.write(self.style.SUCCESS("✅ Cleared\n"))
            else:
                self.stdout.write(self.style.ERROR(f"❌ {existing} schedules exist!"))
                self.stdout.write(f"Use: --clear-existing to delete them\n")
                return
        
        # Get resources
        buses = list(Bus.objects.all().order_by('id'))
        routes = list(Route.objects.all().order_by('id'))
        drivers = list(CustomUser.objects.filter(role='driver').order_by('id'))
        
        if not buses or not routes or not drivers:
            self.stdout.write(self.style.ERROR('❌ Need buses, routes, and drivers!'))
            return
        
        self.stdout.write(f"✅ Found {len(buses)} buses, {len(routes)} routes, {len(drivers)} drivers\n")
        
        # Assign drivers to buses (one-to-one mapping)
        bus_driver_map = {}
        for i, bus in enumerate(buses):
            bus_driver_map[bus] = drivers[i % len(drivers)]
        
        # Trip times (5 trips per day)
        trip_times = [
            (time(6, 0), time(7, 30)),    # Trip 1
            (time(9, 0), time(10, 30)),   # Trip 2
            (time(12, 0), time(13, 30)),  # Trip 3
            (time(15, 0), time(16, 30)),  # Trip 4
            (time(18, 0), time(19, 30)),  # Trip 5
        ]
        
        total_schedules = 0
        
        # Generate schedules for each day
        for day_offset in range(7):
            current_date = week_start + timedelta(days=day_offset)
            day_name = current_date.strftime('%A')
            
            self.stdout.write(f"\n📅 {day_name} ({current_date})")
            
            # Create balanced daily schedule
            daily_assignments = self.create_balanced_daily_schedule(
                buses, routes, current_date, day_offset
            )
            
            # Create schedules
            day_count = 0
            for bus_idx, bus in enumerate(buses):
                driver = bus_driver_map[bus]
                route_assignments = daily_assignments[bus_idx]
                
                for trip_idx, (departure, arrival) in enumerate(trip_times):
                    route = route_assignments[trip_idx]
                    
                    # Calculate passengers (varies by route quality)
                    route_multiplier = self.get_route_multiplier(route, routes)
                    base_passengers = int(bus.capacity * 0.7)
                    passengers = int(base_passengers * route_multiplier * random.uniform(0.85, 1.15))
                    passengers = min(passengers, bus.capacity)
                    
                    Schedule.objects.create(
                        bus=bus,
                        route=route,
                        driver=driver,
                        date=current_date,
                        departure_time=departure,
                        arrival_time=arrival,
                        total_seats=bus.capacity,
                        available_seats=bus.capacity - passengers,
                    )
                    
                    total_schedules += 1
                    day_count += 1
                
                # Spare bus time (staggered)
                spare_hour = 10 + (bus_idx % 10)
                SpareBusSchedule.objects.create(
                    bus=bus,
                    date=current_date,
                    spare_start_time=time(spare_hour % 24, 0),
                    spare_end_time=time((spare_hour + 1) % 24, 0),
                    is_active=True
                )
            
            # Show sample for first bus
            if day_offset == 0:
                self.stdout.write(f"   Sample - {buses[0].number_plate}:")
                for trip_idx, route in enumerate(daily_assignments[0]):
                    self.stdout.write(f"      Trip {trip_idx + 1}: Route {route.number}")
            
            self.stdout.write(f"   Created {day_count} schedules")
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Created {total_schedules} schedules!"))
        self.stdout.write(f"\n💡 Next steps:")
        self.stdout.write(f"   1. View schedules: /zonal-admin/schedules/")
        self.stdout.write(f"   2. End of week: python manage.py calculate_weekly_profits")
        self.stdout.write(f"   3. View profits: /zonal-admin/weekly-profit/")
        self.stdout.write("")
    
    def create_balanced_daily_schedule(self, buses, routes, current_date, day_offset):
        """
        Create balanced schedule where each bus does 2-3 trips per route.
        
        Pattern for 5 trips, 5 routes:
        - Route A: 2 trips (trips 1-2)
        - Route B: 2 trips (trips 3-4)
        - Route C: 1 trip (trip 5)
        
        Each day rotates starting position for fairness.
        """
        num_buses = len(buses)
        num_routes = len(routes)
        
        daily_assignments = []
        
        for bus_idx in range(num_buses):
            # Calculate starting route for this bus on this day
            # Rotates each day + different start per bus
            start_route_idx = (bus_idx + day_offset) % num_routes
            
            # Assign 5 trips with 2-2-1 pattern
            route_schedule = []
            
            # Trip 1-2: First route (2 trips)
            route1_idx = start_route_idx % num_routes
            route_schedule.append(routes[route1_idx])
            route_schedule.append(routes[route1_idx])
            
            # Trip 3-4: Second route (2 trips)
            route2_idx = (start_route_idx + 1) % num_routes
            route_schedule.append(routes[route2_idx])
            route_schedule.append(routes[route2_idx])
            
            # Trip 5: Third route (1 trip)
            route3_idx = (start_route_idx + 2) % num_routes
            route_schedule.append(routes[route3_idx])
            
            daily_assignments.append(route_schedule)
        
        return daily_assignments
    
    def get_route_multiplier(self, route, all_routes):
        """Calculate route quality multiplier for passenger simulation"""
        route_idx = all_routes.index(route)
        num_routes = len(all_routes)
        
        # Create gradient: first route = 1.5x, last route = 0.7x
        multiplier = 1.5 - (route_idx * 0.8 / max(num_routes - 1, 1))
        return round(multiplier, 2)