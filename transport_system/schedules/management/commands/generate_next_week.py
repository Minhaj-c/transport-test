# schedules/management/commands/generate_next_week.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, time, timedelta
import random
from decimal import Decimal

from schedules.models import (
    Bus, Schedule, WeeklyBusPerformance, 
    BusRouteAssignment, SpareBusSchedule
)
from routes.models import Route
from users.models import CustomUser


class Command(BaseCommand):
    help = 'Generate next week schedule with FAIR ROTATION based on last week profits'

    def add_arguments(self, parser):
        parser.add_argument(
            '--week-start',
            type=str,
            required=True,
            help='Next week start date (YYYY-MM-DD)'
        )

    def handle(self, *args, **options):
        next_week_start = date.fromisoformat(options['week_start'])
        next_week_end = next_week_start + timedelta(days=6)
        last_week_start = next_week_start - timedelta(days=7)
        last_week_end = next_week_start - timedelta(days=1)
        
        self.stdout.write(f"\n📅 Generating schedules for: {next_week_start} to {next_week_end}")
        self.stdout.write(f"📊 Based on performance from: {last_week_start} to {last_week_end}\n")
        
        # Get last week's performance
        performances = WeeklyBusPerformance.objects.filter(
            week_start_date=last_week_start
        ).select_related('bus').order_by('total_profit')  # ASCENDING: lowest profit first
        
        if not performances.exists():
            self.stdout.write(self.style.ERROR('❌ No performance data for last week!'))
            self.stdout.write('💡 Run: python manage.py generate_week_demo first')
            return
        
        # Get routes
        routes = list(Route.objects.all())
        
        if not routes:
            self.stdout.write(self.style.ERROR('❌ No routes found!'))
            return
        
        # Calculate route profitability scores (same as generate_week_demo)
        route_profit_scores = {}
        num_routes = len(routes)
        for i, route in enumerate(routes):
            multiplier = 1.5 - (i * 0.8 / max(num_routes - 1, 1))
            route_profit_scores[route] = round(multiplier, 2)
        
        # Sort routes by profitability (best first)
        sorted_routes = sorted(routes, key=lambda r: route_profit_scores.get(r, 1.0), reverse=True)
        
        # Get drivers (keep same driver assignments if possible)
        drivers = list(CustomUser.objects.filter(role='driver'))
        
        if not drivers:
            self.stdout.write(self.style.ERROR('❌ No drivers found!'))
            return
        
        # Get last week's driver assignments
        last_week_schedules = Schedule.objects.filter(
            date__gte=last_week_start,
            date__lte=last_week_end
        ).select_related('bus', 'driver')
        
        # Map: bus -> driver (from last week)
        bus_driver_map = {}
        for schedule in last_week_schedules:
            if schedule.bus not in bus_driver_map:
                bus_driver_map[schedule.bus] = schedule.driver
        
        # FAIR ROTATION ALGORITHM
        self.stdout.write("🔄 FAIR ROTATION ASSIGNMENTS:\n")
        self.stdout.write("="*80)
        
        assignments = []
        
        for i, performance in enumerate(performances):
            bus = performance.bus
            
            # Assign route: lowest profit bus gets best route
            route = sorted_routes[i % len(sorted_routes)]
            
            # Keep same driver if possible, otherwise assign new one
            driver = bus_driver_map.get(bus, drivers[i % len(drivers)])
            
            # Reason
            if performance.profit_rank <= 5:
                reason = f"Ranked #{performance.profit_rank} (LOW profit ₹{performance.total_profit:,.2f} last week) → Assigned HIGH profit route {route.number}"
            elif performance.profit_rank >= len(performances) - 5:
                reason = f"Ranked #{performance.profit_rank} (HIGH profit ₹{performance.total_profit:,.2f} last week) → Assigned LOWER profit route {route.number}"
            else:
                reason = f"Ranked #{performance.profit_rank} (₹{performance.total_profit:,.2f} last week) → Assigned route {route.number}"
            
            expected_profit = Decimal(route_profit_scores[route] * 10000)  # Rough estimate
            
            # Save assignment
            BusRouteAssignment.objects.create(
                bus=bus,
                route=route,
                week_start_date=next_week_start,
                week_end_date=next_week_end,
                assignment_reason=reason,
                expected_profit=expected_profit,
                is_active=True
            )
            
            assignments.append({
                'bus': bus,
                'route': route,
                'driver': driver,
                'last_week_profit': performance.total_profit,
                'last_week_rank': performance.profit_rank,
                'reason': reason
            })
            
            # Print assignment
            if i < 10 or i >= len(performances) - 5:
                self.stdout.write(
                    f"  {bus.number_plate:15} → Route {route.number:3} "
                    f"(Driver: {driver.email[:25]:25}) | {reason[:60]}"
                )
        
        self.stdout.write("="*80 + "\n")
        
        # Generate actual schedules for the week
        self.stdout.write("📝 Creating schedules...\n")
        
        total_schedules = 0
        
        for day_offset in range(7):
            current_date = next_week_start + timedelta(days=day_offset)
            day_name = current_date.strftime('%A')
            
            day_count = 0
            for bus_idx, assignment in enumerate(assignments):
                bus = assignment['bus']
                route = assignment['route']
                driver = assignment['driver']
                
                # Create 5 trips per day
                trip_times = [
                    (time(6, 0), time(7, 30)),
                    (time(9, 0), time(10, 30)),
                    (time(12, 0), time(13, 30)),
                    (time(15, 0), time(16, 30)),
                    (time(18, 0), time(19, 30)),
                ]
                
                for departure, arrival in trip_times:
                    # Calculate expected passengers based on route quality
                    multiplier = route_profit_scores.get(route, 1.0)
                    base_passengers = int(bus.capacity * 0.7)
                    passengers = int(base_passengers * multiplier * random.uniform(0.8, 1.2))
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
                
                # Spare bus schedule (staggered)
                spare_hour = 10 + (bus_idx % 10)
                SpareBusSchedule.objects.create(
                    bus=bus,
                    date=current_date,
                    spare_start_time=time(spare_hour % 24, 0),
                    spare_end_time=time((spare_hour + 1) % 24, 0),
                    is_active=True
                )
            
            if day_offset == 0:  # Only show for first day
                self.stdout.write(f"   {day_name}: Created {day_count} schedules")
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Created {total_schedules} schedules!"))
        self.stdout.write(self.style.SUCCESS(f"✅ Created {len(assignments) * 7} spare bus entries!"))
        
        # Show expected profit changes
        self.stdout.write("\n📈 EXPECTED PROFIT CHANGES (Bottom 5 earners):\n")
        self.stdout.write("="*80)
        
        for assignment in assignments[:5]:  # Show top 5 low earners from last week
            expected = assignment['route'].total_distance * 500  # Rough estimate
            self.stdout.write(
                f"  {assignment['bus'].number_plate}: "
                f"₹{assignment['last_week_profit']:,.2f} last week → "
                f"₹{expected:,.2f} expected (Route {assignment['route'].number})"
            )
        
        self.stdout.write("\n" + "="*80)
        
        self.stdout.write(self.style.SUCCESS("\n🎉 Next week schedule generated!"))
        self.stdout.write(f"\n💡 Next steps:")
        self.stdout.write(f"   1. View profit dashboard: /zonal-admin/weekly-profit/")
        self.stdout.write(f"   2. Schedules are now in database")
        self.stdout.write(f"   3. Flutter driver app will see schedules via API")
        self.stdout.write(f"   4. At end of week, run: python manage.py calculate_weekly_profits --week-start={next_week_start}")
        self.stdout.write("")