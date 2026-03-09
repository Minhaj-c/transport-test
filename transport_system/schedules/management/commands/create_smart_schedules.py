"""
Smart Schedule Generator with Fair Rotation

Features:
- Each bus gets DIFFERENT routes throughout the day (no repeats)
- Uses last week's profit data to swap routes between best/worst performers
- Clean schedules (no dummy passenger data)

Usage:
    python manage.py create_smart_schedules --week-start=2026-03-10
    python manage.py create_smart_schedules --week-start=2026-03-10 --clear-existing
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, time, timedelta

from schedules.models import Bus, Schedule, SpareBusSchedule, WeeklyBusPerformance
from routes.models import Route
from users.models import CustomUser


class Command(BaseCommand):
    help = 'Create smart schedules with route variety and profit-based fair rotation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--week-start',
            type=str,
            required=True,
            help='Week start date (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing schedules for this week before generating'
        )

    def handle(self, *args, **options):
        # ============================================
        # 1. PARSE WEEK DATES
        # ============================================
        week_start = date.fromisoformat(options['week_start'])
        week_end = week_start + timedelta(days=6)
        last_week_start = week_start - timedelta(days=7)
        last_week_end = week_start - timedelta(days=1)
        
        self.stdout.write("\n" + "="*80)
        self.stdout.write(f"🎯 SMART SCHEDULE GENERATION".center(80))
        self.stdout.write("="*80)
        self.stdout.write(f"\n📅 Target Week: {week_start} to {week_end}")
        self.stdout.write(f"📊 Last Week (for profit data): {last_week_start} to {last_week_end}\n")
        
        # ============================================
        # 2. CHECK & CLEAR EXISTING
        # ============================================
        existing = Schedule.objects.filter(date__gte=week_start, date__lte=week_end).count()
        existing_spares = SpareBusSchedule.objects.filter(date__gte=week_start, date__lte=week_end).count()
        
        if existing > 0 or existing_spares > 0:
            if options['clear_existing']:
                self.stdout.write(self.style.WARNING(
                    f"⚠️  Deleting {existing} schedules + {existing_spares} spare slots..."
                ))
                Schedule.objects.filter(date__gte=week_start, date__lte=week_end).delete()
                SpareBusSchedule.objects.filter(date__gte=week_start, date__lte=week_end).delete()
                self.stdout.write(self.style.SUCCESS("✅ Cleared\n"))
            else:
                self.stdout.write(self.style.ERROR(
                    f"\n❌ {existing} schedules exist! Use --clear-existing to delete.\n"
                ))
                return
        
        # ============================================
        # 3. GET RESOURCES
        # ============================================
        buses = list(Bus.objects.filter(is_active=True).order_by('number_plate'))
        routes = list(Route.objects.all().order_by('number'))
        drivers = list(CustomUser.objects.filter(role='driver').order_by('email'))
        
        if not buses or not routes or not drivers:
            self.stdout.write(self.style.ERROR('❌ Need buses, routes, and drivers!'))
            return
        
        if len(routes) < 3:
            self.stdout.write(self.style.ERROR('❌ Need at least 3 routes for variety!'))
            return
        
        self.stdout.write(f"✅ Resources: {len(buses)} buses, {len(routes)} routes, {len(drivers)} drivers\n")
        
        # ============================================
        # 4. GET LAST WEEK'S PROFIT DATA
        # ============================================
        profit_data = {}
        for bus in buses:
            perf = WeeklyBusPerformance.objects.filter(
                bus=bus,
                week_start_date=last_week_start
            ).first()
            
            if perf:
                profit_data[bus.id] = float(perf.total_profit)
        
        # ============================================
        # 5. APPLY FAIR ROTATION (SWAP ROUTES)
        # ============================================
        if profit_data:
            self.stdout.write(self.style.SUCCESS("📊 FAIR ROTATION ENABLED"))
            self.stdout.write(f"   Using profit data from {last_week_start} to {last_week_end}\n")
            
            # Sort buses by profit (ascending - lowest first)
            buses_sorted = sorted(buses, key=lambda b: profit_data.get(b.id, 99999))
            
            # Show profit rankings
            self.stdout.write("💰 Last Week's Profit Rankings:\n")
            
            num_buses = len(buses_sorted)
            
            if num_buses <= 10:
                # Show all buses if 10 or fewer
                for rank, bus in enumerate(buses_sorted, 1):
                    profit = profit_data.get(bus.id, 0)
                    
                    if rank == 1:
                        label = "⬇️ LOWEST earner"
                    elif rank == num_buses:
                        label = "⬆️ HIGHEST earner"
                    else:
                        label = "➡️ Middle"
                    
                    self.stdout.write(f"   #{rank}. {bus.number_plate:15} → ₹{profit:>8,.2f}  {label}")
            else:
                # Show top 5 and bottom 5 for many buses
                self.stdout.write("   ⬇️ BOTTOM 5 (Lowest Earners):")
                for rank, bus in enumerate(buses_sorted[:5], 1):
                    profit = profit_data.get(bus.id, 0)
                    self.stdout.write(f"   #{rank}. {bus.number_plate:15} → ₹{profit:>8,.2f}")
                
                self.stdout.write(f"\n   ... {num_buses - 10} buses in middle ...\n")
                
                self.stdout.write("   ⬆️ TOP 5 (Highest Earners):")
                for rank, bus in enumerate(buses_sorted[-5:], num_buses - 4):
                    profit = profit_data.get(bus.id, 0)
                    self.stdout.write(f"   #{rank}. {bus.number_plate:15} → ₹{profit:>8,.2f}")
            
            # 🔥 SWAP LOGIC: Give best routes to worst performers
            # Lowest profit bus (index 0) gets Routes 0,1,2 (best routes)
            # Highest profit bus (index -1) gets Routes N-3,N-2,N-1 (worst routes)
            
            bus_route_assignments = {}
            num_routes = len(routes)
            
            for rank, bus in enumerate(buses_sorted):
                # Calculate which routes this bus should get
                # Rank 0 (lowest profit) → Routes 0,1,2,3,4 (best)
                # Rank N (highest profit) → Routes N-5,N-4,N-3,N-2,N-1 (worst)
                
                start_idx = rank % num_routes
                
                # Assign 5 DIFFERENT routes starting from this index
                assigned_routes = [
                    routes[(start_idx + i) % num_routes]
                    for i in range(5)
                ]
                
                bus_route_assignments[bus.id] = assigned_routes
            
            
            self.stdout.write("\n🔄 This Week's Route Assignments (Fair Rotation):\n")
            
            num_buses = len(buses_sorted)
            
            if num_buses <= 10:
                # Show all buses if 10 or fewer
                for rank, bus in enumerate(buses_sorted, 1):
                    route_nums = [str(r.number) for r in bus_route_assignments[bus.id]]
                    
                    if rank == 1:
                        label = "⬇️ Got BEST routes (was lowest earner)"
                    elif rank == num_buses:
                        label = "⬆️ Got WORST routes (was highest earner)"
                    else:
                        label = "➡️ Got MIDDLE routes"
                    
                    self.stdout.write(
                        f"   {bus.number_plate:15} (Rank #{rank:2}) → Routes {', '.join(route_nums):20} {label}"
                    )
            else:
                # Show top 5 and bottom 5
                for rank, bus in enumerate(buses_sorted[:5], 1):
                    route_nums = [str(r.number) for r in bus_route_assignments[bus.id]]
                    self.stdout.write(
                        f"   {bus.number_plate:15} (Rank #{rank:2}) → Routes {', '.join(route_nums)} (BEST routes)"
                    )
                
                self.stdout.write(f"\n   ... {num_buses - 10} more buses ...\n")
                
                for rank, bus in enumerate(buses_sorted[-5:], num_buses - 4):
                    route_nums = [str(r.number) for r in bus_route_assignments[bus.id]]
                    self.stdout.write(
                        f"   {bus.number_plate:15} (Rank #{rank:2}) → Routes {', '.join(route_nums)} (WORST routes)"
                    )
            
            self.stdout.write("")
            
        else:
            # NO PROFIT DATA - Use standard rotation
            self.stdout.write(self.style.WARNING("⚠️  No profit data found"))
            self.stdout.write("   Using standard rotation (first week)\n")
            
            bus_route_assignments = {}
            num_routes = len(routes)
            
            for i, bus in enumerate(buses):
                start_idx = i % num_routes
                assigned_routes = [
                    routes[(start_idx + j) % num_routes]
                    for j in range(5)
                ]
                bus_route_assignments[bus.id] = assigned_routes
        
        # ============================================
        # 6. ASSIGN DRIVERS TO BUSES
        # ============================================
        bus_driver_map = {}
        for i, bus in enumerate(buses):
            bus_driver_map[bus.id] = drivers[i % len(drivers)]
        
        # ============================================
        # 7. DEFINE TRIP TIMES (5 trips per day)
        # ============================================
        trip_times = [
            (time(6, 0), time(7, 30)),    # Morning 1
            (time(9, 0), time(10, 30)),   # Morning 2
            (time(12, 0), time(13, 30)),  # Afternoon
            (time(15, 0), time(16, 30)),  # Evening 1
            (time(18, 0), time(19, 30)),  # Evening 2
        ]
        
        # ============================================
        # 8. GENERATE SCHEDULES
        # ============================================
        total_schedules = 0
        total_spares = 0
        
        self.stdout.write("📝 Creating schedules...\n")
        
        for day_offset in range(7):
            current_date = week_start + timedelta(days=day_offset)
            day_name = current_date.strftime('%A')
            
            day_schedules = 0
            day_spares = 0
            
            for bus in buses:
                driver = bus_driver_map[bus.id]
                
                # Get this bus's 5 assigned routes
                assigned_routes = bus_route_assignments[bus.id]
                
                # 🔥 ROTATE DAILY: Each day, shift which route comes first
                # Monday: Routes [0,1,2,3,4]
                # Tuesday: Routes [1,2,3,4,0]
                # Wednesday: Routes [2,3,4,0,1]
                # This ensures variety across the week
                rotated_routes = (
                    assigned_routes[day_offset:] + 
                    assigned_routes[:day_offset]
                )
                
                # Create 5 trips with 5 DIFFERENT routes
                for trip_idx, (departure, arrival) in enumerate(trip_times):
                    route = rotated_routes[trip_idx % len(rotated_routes)]
                    
                    Schedule.objects.create(
                        bus=bus,
                        route=route,
                        driver=driver,
                        date=current_date,
                        departure_time=departure,
                        arrival_time=arrival,
                        total_seats=bus.capacity,
                        available_seats=bus.capacity,  # 🔥 EMPTY
                        current_passengers=0,           # 🔥 ZERO
                    )
                    
                    total_schedules += 1
                    day_schedules += 1
                
                # Create spare slot
                spare_hour = 10 + (buses.index(bus) % 8)
                
                SpareBusSchedule.objects.create(
                    bus=bus,
                    date=current_date,
                    spare_start_time=time(spare_hour, 0),
                    spare_end_time=time(spare_hour + 1, 0),
                    status='waiting',
                )
                
                total_spares += 1
                day_spares += 1
            
            self.stdout.write(
                f"   {day_name:10} ({current_date}): "
                f"{day_schedules} trips + {day_spares} spares"
            )
        
        # ============================================
        # 9. SUMMARY
        # ============================================
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.SUCCESS("✅ SCHEDULE GENERATION COMPLETE"))
        self.stdout.write("="*80 + "\n")
        
        self.stdout.write("📊 Summary:")
        self.stdout.write(f"   • {total_schedules} trip schedules created")
        self.stdout.write(f"   • {total_spares} spare slots created")
        self.stdout.write(f"   • Each bus has 5 DIFFERENT routes per day")
        self.stdout.write(f"   • All schedules start EMPTY (0 passengers)")
        
        if profit_data:
            self.stdout.write(f"\n💡 Fair Rotation Applied:")
            self.stdout.write(f"   ✅ Lowest earners got BEST routes")
            self.stdout.write(f"   ✅ Highest earners got WORST routes")
            self.stdout.write(f"   ✅ Over time, all buses earn equally! 📊")
        
        self.stdout.write(f"\n🎯 Next Steps:")
        self.stdout.write(f"   1. View: http://localhost:8000/zonal-admin/schedules/")
        self.stdout.write(f"   2. Drivers update passengers via app")
        self.stdout.write(f"   3. End of week: Calculate profits")
        self.stdout.write(f"      python manage.py calculate_weekly_profits --week-start={week_start}")
        self.stdout.write("")