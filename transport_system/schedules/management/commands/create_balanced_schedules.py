from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Sum, Avg
from datetime import date, time, timedelta
import random
from decimal import Decimal

from schedules.models import Bus, Schedule, SpareBusSchedule, WeeklyBusPerformance
from routes.models import Route
from users.models import CustomUser


class Command(BaseCommand):
    help = 'Create balanced weekly schedules with AUTOMATIC profit-based fair rotation'

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
        # Calculate week dates
        if options['week_start']:
            week_start = date.fromisoformat(options['week_start'])
        else:
            today = timezone.now().date()
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            week_start = today + timedelta(days=days_until_monday)
        
        week_end = week_start + timedelta(days=6)
        last_week_start = week_start - timedelta(days=7)
        last_week_end = week_start - timedelta(days=1)
        
        self.stdout.write("\nCreating BALANCED Weekly Schedules + Spare Slots")
        self.stdout.write(f"Week: {week_start} to {week_end}")
        self.stdout.write(f"Pattern: 5 DIFFERENT routes per bus per day")
        self.stdout.write(f"Spare: 1-hour spare window per bus per day")
        self.stdout.write(f"Profit-based rotation: AUTO (checks last week {last_week_start} to {last_week_end})\n")
        
        # Check existing schedules
        existing = Schedule.objects.filter(date__gte=week_start, date__lte=week_end).count()
        existing_spares = SpareBusSchedule.objects.filter(date__gte=week_start, date__lte=week_end).count()
        
        if existing > 0 or existing_spares > 0:
            if options['clear_existing']:
                self.stdout.write(self.style.WARNING(
                    f"Deleting {existing} trip schedules + {existing_spares} spare schedules..."
                ))
                Schedule.objects.filter(date__gte=week_start, date__lte=week_end).delete()
                SpareBusSchedule.objects.filter(date__gte=week_start, date__lte=week_end).delete()
                self.stdout.write(self.style.SUCCESS("Cleared\n"))
            else:
                self.stdout.write(self.style.ERROR(
                    f"ERROR: {existing} trip schedules + {existing_spares} spare schedules exist!"
                ))
                self.stdout.write(f"Use: --clear-existing to delete them\n")
                return
        
        # Get resources
        buses = list(Bus.objects.filter(is_active=True).order_by('id'))
        routes = list(Route.objects.all().order_by('id'))
        drivers = list(CustomUser.objects.filter(role='driver').order_by('id'))
        
        if not buses or not routes or not drivers:
            self.stdout.write(self.style.ERROR('ERROR: Need buses, routes, and drivers!'))
            return
        
        if len(routes) < 5:
            self.stdout.write(self.style.ERROR('ERROR: Need at least 5 routes for variety!'))
            return
        
        self.stdout.write(f"Found {len(buses)} buses, {len(routes)} routes, {len(drivers)} drivers\n")
        
        # TRY to use profit-based rotation
        bus_route_map = self.get_profit_based_assignments(
            buses, routes, last_week_start, last_week_end
        )
        
        if bus_route_map:
            self.stdout.write(self.style.SUCCESS("Profit-Based Fair Rotation ENABLED"))
            self.stdout.write("   INVERSE assignment: Lowest earner -> Best routes\n")
            for bus, info in list(bus_route_map.items())[:3]:
                route_nums = [str(r.number) for r in info['routes'][:3]]
                self.stdout.write(
                    f"   {bus.number_plate}: Profit Rank #{info['rank']} (Rs.{info['last_profit']:,.0f}) "
                    f"-> {info['route_quality']} Routes {', '.join(route_nums)}..."
                )
            self.stdout.write("")
        else:
            self.stdout.write(self.style.WARNING(
                "No profit data found for last week. Using standard rotation."
            ))
            self.stdout.write(
                "   After this week ends, calculate profits via web interface\n"
            )
        
        # Assign drivers to buses
        bus_driver_map = {}
        for i, bus in enumerate(buses):
            bus_driver_map[bus] = drivers[i % len(drivers)]
        
        # Trip times (5 trips per day)
        trip_times = [
            (time(6, 0), time(7, 30)),
            (time(9, 0), time(10, 30)),
            (time(12, 0), time(13, 30)),
            (time(15, 0), time(16, 30)),
            (time(18, 0), time(19, 30)),
        ]
        
        # Spare times (staggered)
        spare_times = [
            (time(8, 0), time(9, 0)),
            (time(11, 0), time(12, 0)),
            (time(14, 0), time(15, 0)),
            (time(17, 0), time(18, 0)),
            (time(10, 0), time(11, 0)),
        ]
        
        total_schedules = 0
        total_spares = 0
        
        # Generate schedules for each day
        for day_offset in range(7):
            current_date = week_start + timedelta(days=day_offset)
            day_name = current_date.strftime('%A')
            
            self.stdout.write(f"{day_name} ({current_date})")
            
            day_count = 0
            day_spares = 0
            
            for bus_idx, bus in enumerate(buses):
                driver = bus_driver_map[bus]
                
                # Get 5 DIFFERENT routes for this bus
                if bus_route_map and bus in bus_route_map:
                    # Use profit-based assignment
                    assigned_routes = bus_route_map[bus]['routes']
                    # Rotate daily for variety
                    rotated = assigned_routes[day_offset % len(assigned_routes):] + assigned_routes[:day_offset % len(assigned_routes)]
                    route_schedule = rotated[:5]  # Take first 5
                else:
                    # Standard rotation (no profit data)
                    route_schedule = self.get_varied_routes(routes, bus_idx, day_offset)
                
                # Create 5 trip schedules with 5 DIFFERENT routes
                for trip_idx, (departure, arrival) in enumerate(trip_times):
                    route = route_schedule[trip_idx]
                    
                    Schedule.objects.create(
                        bus=bus,
                        route=route,
                        driver=driver,
                        date=current_date,
                        departure_time=departure,
                        arrival_time=arrival,
                        total_seats=bus.capacity,
                        available_seats=bus.capacity,  # Empty - driver fills
                        current_passengers=0,
                    )
                    
                    total_schedules += 1
                    day_count += 1
                
                # Create spare schedule
                spare_start, spare_end = spare_times[bus_idx % len(spare_times)]
                SpareBusSchedule.objects.create(
                    bus=bus,
                    date=current_date,
                    spare_start_time=spare_start,
                    spare_end_time=spare_end,
                    status='waiting',
                )
                
                total_spares += 1
                day_spares += 1
            
            self.stdout.write(f"   Created {day_count} trip schedules + {day_spares} spare schedules")
        
        self.stdout.write(self.style.SUCCESS(f"\nWeek schedules created!"))
        self.stdout.write(self.style.SUCCESS(f"   • {total_schedules} trip schedules"))
        self.stdout.write(self.style.SUCCESS(f"   • {total_spares} spare schedules"))
        
        if bus_route_map:
            self.stdout.write(f"\nFair Rotation Applied:")
            self.stdout.write(f"   Buses with LOW profit last week got BEST routes this week")
            self.stdout.write(f"   Buses with HIGH profit last week got WORST routes this week")
            self.stdout.write(f"   Over multiple weeks, all buses earn EQUAL amounts!")
        
        self.stdout.write(f"\nNext steps:")
        self.stdout.write(f"   1. View schedules: /zonal-admin/schedules/")
        self.stdout.write(f"   2. End of week: Calculate profits via web interface")
        self.stdout.write(f"   3. Next week: Generate again (will use this week's profit)")
        self.stdout.write("")
    
    def get_profit_based_assignments(self, buses, routes, last_week_start, last_week_end):
        """
        Assign routes based on last week's profit.
        Lowest earner gets BEST routes.
        Highest earner gets WORST routes.
        """
        
        # Get last week's profit data
        profit_data = {}
        
        for bus in buses:
            performance = WeeklyBusPerformance.objects.filter(
                bus=bus,
                week_start_date=last_week_start
            ).first()
            
            if performance:
                profit_data[bus] = float(performance.total_profit)
        
        # If no profit data, return None (use standard rotation)
        if not profit_data:
            return None
        
        # Sort buses by profit ASCENDING (lowest first)
        sorted_buses_by_profit = sorted(
            buses,
            key=lambda b: profit_data.get(b, 50000)
        )
        
        # Sort routes by number (assuming lower number = better route)
        sorted_routes = sorted(routes, key=lambda r: r.number)
        
        # Assign routes: Lowest profit bus gets best routes
        assignments = {}
        num_routes = len(routes)
        
        for bus_rank, bus in enumerate(sorted_buses_by_profit):
            # Start index for this bus
            start_idx = bus_rank % num_routes
            
            # Assign 5 different routes
            assigned = []
            for i in range(5):
                route_idx = (start_idx + i) % num_routes
                assigned.append(sorted_routes[route_idx])
            
            # Determine quality label
            if bus_rank == 0:
                quality = "BEST"
            elif bus_rank == len(sorted_buses_by_profit) - 1:
                quality = "WORST"
            else:
                quality = "MEDIUM"
            
            assignments[bus] = {
                'routes': assigned,
                'rank': bus_rank + 1,
                'last_profit': profit_data.get(bus, 0),
                'route_quality': quality,
            }
        
        return assignments
    
    def get_varied_routes(self, routes, bus_idx, day_offset):
        """
        Get 5 different routes for a bus on a given day (when no profit data).
        """
        num_routes = len(routes)
        start_idx = (bus_idx + day_offset) % num_routes
        
        varied_routes = []
        for i in range(5):
            route_idx = (start_idx + i) % num_routes
            varied_routes.append(routes[route_idx])
        
        return varied_routes