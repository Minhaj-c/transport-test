# schedules/management/commands/generate_week_demo.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, time, timedelta
import random
from decimal import Decimal

from schedules.models import Bus, Schedule, WeeklyBusPerformance, SpareBusSchedule
from routes.models import Route, Stop
from users.models import CustomUser


class Command(BaseCommand):
    help = 'Generate one week of dummy data for demonstration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--week-start',
            type=str,
            help='Week start date (YYYY-MM-DD). Default: next Monday'
        )

    def handle(self, *args, **options):
        # Determine week start
        if options['week_start']:
            week_start = date.fromisoformat(options['week_start'])
        else:
            # Get next Monday
            today = timezone.now().date()
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7  # If today is Monday, get next Monday
            week_start = today + timedelta(days=days_until_monday)
        
        week_end = week_start + timedelta(days=6)
        
        self.stdout.write(f"\n📅 Generating demo data for week: {week_start} to {week_end}\n")
        
        # Get buses, routes, and drivers
        buses = list(Bus.objects.all())
        routes = list(Route.objects.all())
        drivers = list(CustomUser.objects.filter(role='driver'))
        
        if not buses:
            self.stdout.write(self.style.ERROR('❌ No buses found. Create buses first.'))
            return
        
        if not routes:
            self.stdout.write(self.style.ERROR('❌ No routes found. Create routes first.'))
            return
        
        if not drivers:
            self.stdout.write(self.style.ERROR('❌ No drivers found. Create drivers first.'))
            return
        
        self.stdout.write(f"✅ Found {len(buses)} buses, {len(routes)} routes, {len(drivers)} drivers\n")
        
        # Define route profitability based on actual number of routes
        # Create profit multipliers dynamically
        route_profit_multiplier = {}
        num_routes = len(routes)
        
        # Distribute profitability from high to low
        for i, route in enumerate(routes):
            # Create gradient: first route = 1.5x, last route = 0.7x
            multiplier = 1.5 - (i * 0.8 / max(num_routes - 1, 1))
            route_profit_multiplier[route] = round(multiplier, 2)
        
        # Initial bus-route-driver assignments
        assignments = {}
        for i, bus in enumerate(buses):
            route = routes[i % len(routes)]
            driver = drivers[i % len(drivers)]
            assignments[bus] = {
                'route': route,
                'driver': driver
            }
        
        self.stdout.write("\n📋 Week Assignments:")
        for i, (bus, assignment) in enumerate(list(assignments.items())[:10]):  # Show first 10
            multiplier = route_profit_multiplier[assignment['route']]
            self.stdout.write(
                f"   {bus.number_plate:15} → Route {assignment['route'].number:3} "
                f"(Driver: {assignment['driver'].email[:20]:20}) "
                f"(Profit x{multiplier})"
            )
        if len(assignments) > 10:
            self.stdout.write(f"   ... and {len(assignments) - 10} more")
        
        # Generate 7 days of schedules
        total_schedules = 0
        
        for day_offset in range(7):  # Monday to Sunday
            current_date = week_start + timedelta(days=day_offset)
            day_name = current_date.strftime('%A')
            
            self.stdout.write(f"\n🗓️  Generating {day_name} ({current_date})...")
            
            day_count = 0
            for bus, assignment in assignments.items():
                route = assignment['route']
                driver = assignment['driver']
                
                # Create 5 trips per day
                trip_times = [
                    (time(6, 0), time(7, 30)),    # 6:00 AM - 7:30 AM
                    (time(9, 0), time(10, 30)),   # 9:00 AM - 10:30 AM
                    (time(12, 0), time(13, 30)),  # 12:00 PM - 1:30 PM
                    (time(15, 0), time(16, 30)),  # 3:00 PM - 4:30 PM
                    (time(18, 0), time(19, 30)),  # 6:00 PM - 7:30 PM
                ]
                
                for departure, arrival in trip_times:
                    # Calculate passengers (influenced by route quality)
                    multiplier = route_profit_multiplier[route]
                    base_passengers = int(bus.capacity * 0.7)  # 70% average occupancy
                    passengers = int(base_passengers * multiplier * random.uniform(0.8, 1.2))
                    passengers = min(passengers, bus.capacity)  # Can't exceed capacity
                    
                    # Create schedule
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
                
                # Create spare bus schedule (1 hour per day, staggered)
                bus_index = list(assignments.keys()).index(bus)
                spare_hour = 10 + (bus_index % 10)  # 10 AM, 11 AM, 12 PM, etc.
                
                # Make sure spare hour doesn't conflict with trips
                # If it does, shift to available hour
                spare_time = time(spare_hour % 24, 0)
                
                SpareBusSchedule.objects.create(
                    bus=bus,
                    date=current_date,
                    spare_start_time=spare_time,
                    spare_end_time=time((spare_hour + 1) % 24, 0),
                    is_active=True
                )
            
            self.stdout.write(f"   Created {day_count} schedules")
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Created {total_schedules} schedules for the week!"))
        self.stdout.write(self.style.SUCCESS(f"✅ Created {len(buses) * 7} spare bus entries!\n"))
        
        # Calculate weekly performance
        self.stdout.write("📊 Calculating weekly performance...\n")
        self.calculate_performance(week_start, week_end, assignments, route_profit_multiplier)
        
        self.stdout.write(self.style.SUCCESS("\n🎉 Demo data generation complete!"))
        self.stdout.write(f"\n💡 Next steps:")
        self.stdout.write(f"   1. View schedules: /zonal-admin/schedules/")
        self.stdout.write(f"   2. View profit dashboard: /zonal-admin/weekly-profit/")
        self.stdout.write(f"   3. Generate next week: python manage.py generate_next_week --week-start={week_end + timedelta(days=1)}")
        self.stdout.write("")
    
    def calculate_performance(self, week_start, week_end, assignments, route_multipliers):
        """Calculate and display weekly performance for each bus"""
        
        bus_profits = []
        
        for bus, assignment in assignments.items():
            route = assignment['route']
            
            # Get all schedules for this bus this week
            schedules = Schedule.objects.filter(
                bus=bus,
                date__gte=week_start,
                date__lte=week_end
            )
            
            # Calculate metrics
            total_trips = schedules.count()
            
            # Calculate passengers (from available_seats)
            total_passengers = sum(
                s.total_seats - s.available_seats 
                for s in schedules
            )
            
            # Calculate revenue (₹25 per passenger)
            total_revenue = Decimal(total_passengers * 25)
            
            # Calculate fuel cost
            total_distance = sum(s.route.total_distance for s in schedules)
            
            # Use bus mileage for fuel calculation
            if bus.mileage > 0:
                fuel_needed = total_distance / bus.mileage  # liters
                total_fuel_cost = Decimal(fuel_needed * 100)  # ₹100 per liter
            else:
                # Default mileage if not set
                fuel_needed = total_distance / 5  # Assume 5 km/l
                total_fuel_cost = Decimal(fuel_needed * 100)
            
            # Calculate profit
            total_profit = total_revenue - total_fuel_cost
            
            # Save performance
            perf, created = WeeklyBusPerformance.objects.update_or_create(
                bus=bus,
                week_start_date=week_start,
                defaults={
                    'week_end_date': week_end,
                    'total_trips': total_trips,
                    'total_passengers': total_passengers,
                    'total_distance_km': total_distance,
                    'total_revenue': total_revenue,
                    'total_fuel_cost': total_fuel_cost,
                    'total_profit': total_profit,
                }
            )
            
            bus_profits.append((bus, route, total_profit))
        
        # Rank buses by profit
        bus_profits.sort(key=lambda x: x[2], reverse=True)
        
        for rank, (bus, route, profit) in enumerate(bus_profits, 1):
            WeeklyBusPerformance.objects.filter(
                bus=bus,
                week_start_date=week_start
            ).update(profit_rank=rank)
        
        # Display top performers
        display_count = min(5, len(bus_profits))
        self.stdout.write(f"\n🏆 Top {display_count} Buses by Profit:")
        for rank, (bus, route, profit) in enumerate(bus_profits[:display_count], 1):
            self.stdout.write(f"   {rank}. {bus.number_plate} (Route {route.number}): ₹{profit:,.2f}")
        
        # Display bottom performers
        if len(bus_profits) > 5:
            self.stdout.write(f"\n📉 Bottom {display_count} Buses by Profit:")
            for rank, (bus, route, profit) in enumerate(bus_profits[-display_count:], len(bus_profits)-display_count+1):
                self.stdout.write(f"   {rank}. {bus.number_plate} (Route {route.number}): ₹{profit:,.2f}")