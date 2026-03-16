"""
Smart Schedule Generator with Fair Rotation + Return Trips

Features:
- Each bus gets DIFFERENT routes throughout the day
- Forward trip (A→F) followed by return trip (F→A) using reverse route
- 10 min turnaround between forward and return
- Uses last week's profit data for fair rotation
- Clean schedules (0 passengers)

Usage:
    python manage.py create_balanced_schedules --week-start=2026-03-10
    python manage.py create_balanced_schedules --week-start=2026-03-10 --clear-existing

Prerequisites:
    Run first: python manage.py create_reverse_routes
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, time, timedelta

from schedules.models import Bus, Schedule, SpareBusSchedule, WeeklyBusPerformance
from routes.models import Route
from users.models import CustomUser


class Command(BaseCommand):
    help = 'Create smart schedules with return trips and profit-based fair rotation'

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
        self.stdout.write("🎯 SMART SCHEDULE GENERATION".center(80))
        self.stdout.write("="*80)
        self.stdout.write(f"\n📅 Target Week: {week_start} to {week_end}")
        self.stdout.write(
            f"📊 Last Week (for profit data): {last_week_start} to {last_week_end}\n"
        )

        # ============================================
        # 2. CHECK & CLEAR EXISTING
        # ============================================
        existing = Schedule.objects.filter(
            date__gte=week_start, date__lte=week_end
        ).count()
        existing_spares = SpareBusSchedule.objects.filter(
            date__gte=week_start, date__lte=week_end
        ).count()

        if existing > 0 or existing_spares > 0:
            if options['clear_existing']:
                self.stdout.write(self.style.WARNING(
                    f"⚠️  Deleting {existing} schedules + {existing_spares} spare slots..."
                ))
                Schedule.objects.filter(
                    date__gte=week_start, date__lte=week_end
                ).delete()
                SpareBusSchedule.objects.filter(
                    date__gte=week_start, date__lte=week_end
                ).delete()
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
        drivers = list(CustomUser.objects.filter(role='driver').order_by('email'))

        # ✅ Only forward routes (not reverse routes ending in 'R')
        forward_routes = list(
            Route.objects.exclude(number__endswith='R').order_by('number')
        )

        if not buses or not forward_routes or not drivers:
            self.stdout.write(self.style.ERROR('❌ Need buses, routes, and drivers!'))
            return

        if len(forward_routes) < 3:
            self.stdout.write(self.style.ERROR('❌ Need at least 3 forward routes!'))
            return

        # ✅ Build reverse route map: route.number → reverse Route object
        reverse_route_map = {}
        for route in forward_routes:
            reverse = Route.objects.filter(number=f"{route.number}R").first()
            if reverse:
                reverse_route_map[route.id] = reverse
            else:
                self.stdout.write(self.style.WARNING(
                    f"   ⚠️  No reverse route for {route.number}. "
                    f"Run: python manage.py create_reverse_routes"
                ))

        self.stdout.write(
            f"✅ Resources: {len(buses)} buses, "
            f"{len(forward_routes)} forward routes "
            f"({len(reverse_route_map)} have return routes), "
            f"{len(drivers)} drivers\n"
        )

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
        # 5. APPLY FAIR ROTATION
        # ============================================
        if profit_data:
            self.stdout.write(self.style.SUCCESS("📊 FAIR ROTATION ENABLED"))
            self.stdout.write(
                f"   Using profit data from {last_week_start} to {last_week_end}\n"
            )

            buses_sorted = sorted(
                buses, key=lambda b: profit_data.get(b.id, 99999)
            )

            self.stdout.write("💰 Last Week's Profit Rankings:\n")
            num_buses = len(buses_sorted)

            for rank, bus in enumerate(buses_sorted[:min(num_buses, 10)], 1):
                profit = profit_data.get(bus.id, 0)
                label = (
                    "⬇️ LOWEST earner" if rank == 1
                    else "⬆️ HIGHEST earner" if rank == num_buses
                    else "➡️ Middle"
                )
                self.stdout.write(
                    f"   #{rank}. {bus.number_plate:15} → ₹{profit:>8,.2f}  {label}"
                )

            bus_route_assignments = {}
            num_routes = len(forward_routes)

            for rank, bus in enumerate(buses_sorted):
                start_idx = rank % num_routes
                assigned_routes = [
                    forward_routes[(start_idx + i) % num_routes]
                    for i in range(4)
                ]
                bus_route_assignments[bus.id] = assigned_routes

            self.stdout.write("\n🔄 This Week's Route Assignments:\n")
            for rank, bus in enumerate(buses_sorted[:min(num_buses, 10)], 1):
                route_nums = [str(r.number) for r in bus_route_assignments[bus.id]]
                self.stdout.write(
                    f"   {bus.number_plate:15} (Rank #{rank:2}) → "
                    f"Routes {', '.join(route_nums)}"
                )
            self.stdout.write("")

        else:
            self.stdout.write(self.style.WARNING("⚠️  No profit data found"))
            self.stdout.write("   Using standard rotation (first week)\n")

            bus_route_assignments = {}
            num_routes = len(forward_routes)

            for i, bus in enumerate(buses):
                start_idx = i % num_routes
                assigned_routes = [
                    forward_routes[(start_idx + j) % num_routes]
                    for j in range(4)
                ]
                bus_route_assignments[bus.id] = assigned_routes

        # ============================================
        # 6. ASSIGN DRIVERS TO BUSES
        # ============================================
        bus_driver_map = {}
        for bus in buses:
            permanent_driver = bus.permanent_driver.first()
            if permanent_driver:
                bus_driver_map[bus.id] = permanent_driver
            else:
                idx = buses.index(bus)
                bus_driver_map[bus.id] = drivers[idx % len(drivers)]

        # ============================================
        # 7. TRIP TIMES
        # 4 pairs: forward + 10 min turnaround + return
        # ============================================
        trip_pairs = [
            # (forward_departure, forward_arrival, return_departure, return_arrival)
            (time(6, 0),  time(7, 30),  time(7, 40),  time(9, 10)),
            (time(10, 0), time(11, 30), time(11, 40), time(13, 10)),
            (time(14, 0), time(15, 30), time(15, 40), time(17, 10)),
            (time(18, 0), time(19, 30), time(19, 40), time(21, 10)),
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
                assigned_routes = bus_route_assignments[bus.id]

                # Rotate daily for variety
                rotated_routes = (
                    assigned_routes[day_offset % len(assigned_routes):]
                    + assigned_routes[:day_offset % len(assigned_routes)]
                )

                # Create 4 forward + 4 return trips
                for pair_idx, (fwd_dep, fwd_arr, ret_dep, ret_arr) in enumerate(trip_pairs):
                    forward_route = rotated_routes[pair_idx % len(rotated_routes)]
                    reverse_route = reverse_route_map.get(forward_route.id)

                    # ✅ Forward trip A→F
                    Schedule.objects.create(
                        bus=bus,
                        route=forward_route,
                        driver=driver,
                        date=current_date,
                        departure_time=fwd_dep,
                        arrival_time=fwd_arr,
                        total_seats=bus.capacity,
                        available_seats=bus.capacity,
                        current_passengers=0,
                    )
                    total_schedules += 1
                    day_schedules += 1

                    # ✅ Return trip F→A (only if reverse route exists)
                    if reverse_route:
                        Schedule.objects.create(
                            bus=bus,
                            route=reverse_route,
                            driver=driver,
                            date=current_date,
                            departure_time=ret_dep,
                            arrival_time=ret_arr,
                            total_seats=bus.capacity,
                            available_seats=bus.capacity,
                            current_passengers=0,
                        )
                        total_schedules += 1
                        day_schedules += 1
                    else:
                        self.stdout.write(self.style.WARNING(
                            f"   ⚠️  No return route for {forward_route.number} "
                            f"— skipping return trip"
                        ))

                # ✅ Spare slot (staggered per bus)
                spare_hour = 9 + (buses.index(bus) % 8)
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
        self.stdout.write(f"   • Each bus: 4 forward + 4 return trips per day")
        self.stdout.write(f"   • 10 min turnaround between forward and return")
        self.stdout.write(f"   • All schedules start EMPTY (0 passengers)")

        if profit_data:
            self.stdout.write(f"\n💡 Fair Rotation Applied:")
            self.stdout.write(f"   ✅ Lowest earners got BEST routes")
            self.stdout.write(f"   ✅ Highest earners got WORST routes")

        self.stdout.write(f"\n🎯 Next Steps:")
        self.stdout.write(
            f"   1. View: http://localhost:8000/zonal-admin/schedules/"
        )
        self.stdout.write(f"   2. Drivers update passengers via app")
        self.stdout.write(f"   3. End of week: Calculate profits")
        self.stdout.write("")