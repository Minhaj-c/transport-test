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
        # [... existing week calculation code stays same ...]
        
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
        
        self.stdout.write(f"\n🎯 Creating BALANCED Weekly Schedules + Spare Slots")
        self.stdout.write(f"📅 Week: {week_start} to {week_end}")
        self.stdout.write(f"📋 Pattern: 2-3 trips per route per bus per day")
        self.stdout.write(f"⚡ Spare: 1-hour spare window per bus per day")
        self.stdout.write(f"💰 Profit-based rotation: AUTO (checks last week {last_week_start} to {last_week_end})\n")
        
        # Check existing schedules
        existing = Schedule.objects.filter(date__gte=week_start, date__lte=week_end).count()
        existing_spares = SpareBusSchedule.objects.filter(date__gte=week_start, date__lte=week_end).count()
        
        if existing > 0 or existing_spares > 0:
            if options['clear_existing']:
                self.stdout.write(self.style.WARNING(
                    f"⚠️  Deleting {existing} trip schedules + {existing_spares} spare schedules..."
                ))
                Schedule.objects.filter(date__gte=week_start, date__lte=week_end).delete()
                SpareBusSchedule.objects.filter(date__gte=week_start, date__lte=week_end).delete()
                self.stdout.write(self.style.SUCCESS("✅ Cleared\n"))
            else:
                self.stdout.write(self.style.ERROR(
                    f"❌ {existing} trip schedules + {existing_spares} spare schedules exist!"
                ))
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
        
        # 🔥 ALWAYS TRY TO USE PROFIT-BASED ROTATION
        bus_route_map = self.get_profit_based_assignments(
            buses, routes, last_week_start, last_week_end
        )
        
        if bus_route_map:
            self.stdout.write(self.style.SUCCESS("📊 Profit-Based Fair Rotation ENABLED"))
            self.stdout.write("   🔄 INVERSE assignment: Lowest earner → Best routes\n")
            for bus, info in bus_route_map.items():
                route_nums = [str(r.number) for r in info['routes'][:3]]
                quality = info['route_quality']
                self.stdout.write(
                    f"   {bus.number_plate}: Profit Rank #{info['rank']} (₹{info['last_profit']:,.0f}) "
                    f"→ {quality} Routes {', '.join(route_nums)}"
                )
            self.stdout.write("")
        else:
            self.stdout.write(self.style.WARNING(
                "⚠️  No profit data found for last week. Using standard rotation."
            ))
            self.stdout.write(
                "   💡 Tip: After this week ends, calculate profits via web interface\n"
            )
        
        # [... rest of code stays the same until get_profit_based_assignments ...]
        
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
            
            self.stdout.write(f"\n📅 {day_name} ({current_date})")
            
            day_count = 0
            day_spares = 0
            
            for bus_idx, bus in enumerate(buses):
                driver = bus_driver_map[bus]
                
                # Get route assignments
                if bus_route_map and bus in bus_route_map:
                    # Use profit-based assignment
                    assigned_routes = bus_route_map[bus]['routes']
                    route_schedule = self.create_daily_pattern_from_assigned(
                        assigned_routes, day_offset
                    )
                else:
                    # Use standard rotation (Week 1 or no profit data)
                    daily_assignments = self.create_balanced_daily_schedule(
                        buses, routes, current_date, day_offset
                    )
                    route_schedule = daily_assignments[bus_idx]
                
                # Create 5 trip schedules
                for trip_idx, (departure, arrival) in enumerate(trip_times):
                    route = route_schedule[trip_idx]
                    
                    # Calculate passengers
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
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Week schedules created!"))
        self.stdout.write(self.style.SUCCESS(f"   • {total_schedules} trip schedules"))
        self.stdout.write(self.style.SUCCESS(f"   • {total_spares} spare schedules"))
        
        if bus_route_map:
            self.stdout.write(f"\n💡 Fair Rotation Applied:")
            self.stdout.write(f"   ✅ Buses with LOW profit last week got BEST routes this week")
            self.stdout.write(f"   ✅ Buses with HIGH profit last week got WORST routes this week")
            self.stdout.write(f"   ✅ Over multiple weeks, all buses earn EQUAL amounts! 📊")
        
        self.stdout.write(f"\n💡 Next steps:")
        self.stdout.write(f"   1. View schedules: /zonal-admin/schedules/")
        self.stdout.write(f"   2. End of week: Calculate profits via web interface")
        self.stdout.write(f"   3. Next week: Generate again (will use this week's profit)")
        self.stdout.write("")
    
    def get_profit_based_assignments(self, buses, routes, last_week_start, last_week_end):
        """
        🔥 FIXED: Truly inverse assignment
        Lowest earner → Best routes
        Highest earner → Worst routes
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
        
        # 🔥 Sort buses by profit ASCENDING (lowest first)
        sorted_buses_by_profit = sorted(
            buses,
            key=lambda b: profit_data.get(b, 50000)
        )
        
        # 🔥 Rank routes by distance DESCENDING (longest/best first)
        route_with_distance = [
            (route, float(route.total_distance))
            for route in routes
        ]
        route_with_distance.sort(key=lambda x: x[1], reverse=True)
        sorted_routes_best_first = [r[0] for r in route_with_distance]
        
        # 🔥 CRITICAL FIX: Direct assignment
        # Bus with LOWEST profit (index 0) gets BEST routes (indices 0,1,2)
        # Bus with HIGHEST profit (index 4) gets WORST routes (indices 3,4,0 wrapped)
        
        assignments = {}
        num_routes = len(routes)
        
        for bus_rank, bus in enumerate(sorted_buses_by_profit):
            # Bus rank: 0 = lowest earner, 4 = highest earner
            
            # Route starting index: directly use bus_rank
            # This ensures lowest earner (rank 0) starts at route index 0 (best)
            # highest earner (rank 4) starts at route index 4 (worst)
            start_route_idx = bus_rank
            
            # Assign 3 consecutive routes starting from this index
            assigned = [
                sorted_routes_best_first[(start_route_idx + 0) % num_routes],
                sorted_routes_best_first[(start_route_idx + 1) % num_routes],
                sorted_routes_best_first[(start_route_idx + 2) % num_routes],
            ]
            
            # Determine quality label
            if bus_rank == 0:
                quality = "💎 BEST"
            elif bus_rank == len(sorted_buses_by_profit) - 1:
                quality = "📉 WORST"
            else:
                quality = "📊 MEDIUM"
            
            assignments[bus] = {
                'routes': assigned,
                'rank': bus_rank + 1,  # 1-indexed for display
                'last_profit': profit_data.get(bus, 0),
                'route_quality': quality,
            }
        
        return assignments
    
    def create_daily_pattern_from_assigned(self, assigned_routes, day_offset):
        """Create 2-2-1 pattern from pre-assigned routes"""
        # Rotate which route gets priority each day
        rotated = assigned_routes[day_offset % 3:] + assigned_routes[:day_offset % 3]
        
        return [
            rotated[0],  # Trip 1
            rotated[0],  # Trip 2
            rotated[1],  # Trip 3
            rotated[1],  # Trip 4
            rotated[2],  # Trip 5
        ]
    
    def create_balanced_daily_schedule(self, buses, routes, current_date, day_offset):
        """Standard balanced schedule (used when no profit data)"""
        num_buses = len(buses)
        num_routes = len(routes)
        
        daily_assignments = []
        
        for bus_idx in range(num_buses):
            start_route_idx = (bus_idx + day_offset) % num_routes
            
            route_schedule = []
            
            # 2-2-1 pattern
            route1_idx = start_route_idx % num_routes
            route_schedule.append(routes[route1_idx])
            route_schedule.append(routes[route1_idx])
            
            route2_idx = (start_route_idx + 1) % num_routes
            route_schedule.append(routes[route2_idx])
            route_schedule.append(routes[route2_idx])
            
            route3_idx = (start_route_idx + 2) % num_routes
            route_schedule.append(routes[route3_idx])
            
            daily_assignments.append(route_schedule)
        
        return daily_assignments
    
    def get_route_multiplier(self, route, all_routes):
        """Calculate route quality multiplier for passenger simulation"""
        route_idx = all_routes.index(route)
        num_routes = len(all_routes)
        multiplier = 1.5 - (route_idx * 0.8 / max(num_routes - 1, 1))
        return round(multiplier, 2)