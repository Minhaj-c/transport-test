# schedules/management/commands/calculate_weekly_profits.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from schedules.models import Bus, Schedule, WeeklyBusPerformance


class Command(BaseCommand):
    help = 'Calculate weekly profits for all buses (run at end of week)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--week-start',
            type=str,
            help='Week start date (YYYY-MM-DD). Default: last Monday'
        )

    def handle(self, *args, **options):
        # Determine which week to calculate
        if options['week_start']:
            week_start = date.fromisoformat(options['week_start'])
        else:
            # Default: last completed week (previous Monday)
            today = timezone.now().date()
            days_since_monday = today.weekday()
            
            if days_since_monday == 0:  # Today is Monday
                week_start = today - timedelta(days=7)
            else:
                week_start = today - timedelta(days=days_since_monday)
        
        week_end = week_start + timedelta(days=6)
        
        self.stdout.write(f"\n💰 CALCULATING WEEKLY PROFITS")
        self.stdout.write(f"📅 Week: {week_start} to {week_end}\n")
        
        # Get all buses with schedules this week
        buses_with_schedules = Schedule.objects.filter(
            date__gte=week_start,
            date__lte=week_end
        ).values_list('bus_id', flat=True).distinct()
        
        buses = Bus.objects.filter(id__in=buses_with_schedules).order_by('number_plate')
        
        if not buses.exists():
            self.stdout.write(self.style.WARNING('⚠️  No schedules found for this week!'))
            self.stdout.write(f'📅 Week: {week_start} to {week_end}\n')
            return
        
        self.stdout.write(f"🚌 Analyzing {buses.count()} buses...\n")
        
        bus_profits = []
        
        # Calculate profit for each bus
        for bus in buses:
            profit_data = self.calculate_bus_profit(bus, week_start, week_end)
            bus_profits.append(profit_data)
            
            # Save to database
            WeeklyBusPerformance.objects.update_or_create(
                bus=bus,
                week_start_date=week_start,
                defaults={
                    'week_end_date': week_end,
                    'total_trips': profit_data['trips'],
                    'total_passengers': profit_data['passengers'],
                    'total_distance_km': profit_data['distance'],
                    'total_revenue': profit_data['revenue'],
                    'total_fuel_cost': profit_data['fuel_cost'],
                    'total_profit': profit_data['profit'],
                }
            )
        
        # Rank buses by profit
        bus_profits.sort(key=lambda x: x['profit'], reverse=True)
        
        # Update rankings
        for rank, data in enumerate(bus_profits, 1):
            WeeklyBusPerformance.objects.filter(
                bus=data['bus'],
                week_start_date=week_start
            ).update(profit_rank=rank)
        
        # Display results
        self.stdout.write("="*90)
        self.stdout.write("📊 WEEKLY PROFIT RESULTS".center(90))
        self.stdout.write("="*90)
        self.stdout.write(
            f"{'Rank':<6}{'Bus':<15}{'Trips':<8}{'Passengers':<12}"
            f"{'Revenue':<15}{'Fuel Cost':<15}{'Profit':<15}"
        )
        self.stdout.write("-"*90)
        
        for rank, data in enumerate(bus_profits, 1):
            profit_color = self.style.SUCCESS if data['profit'] > 15000 else (
                self.style.WARNING if data['profit'] > 10000 else self.style.ERROR
            )
            
            self.stdout.write(
                f"{rank:<6}"
                f"{data['bus'].number_plate:<15}"
                f"{data['trips']:<8}"
                f"{data['passengers']:<12}"
                f"₹{data['revenue']:>10,.0f}    "
                f"₹{data['fuel_cost']:>10,.0f}    "
                + profit_color(f"₹{data['profit']:>10,.0f}")
            )
        
        self.stdout.write("="*90)
        
        # Summary statistics
        total_profit = sum(d['profit'] for d in bus_profits)
        avg_profit = total_profit / len(bus_profits) if bus_profits else 0
        total_passengers = sum(d['passengers'] for d in bus_profits)
        
        self.stdout.write(f"\n📈 SUMMARY:")
        self.stdout.write(f"   Total Zone Profit:     ₹{total_profit:,.2f}")
        self.stdout.write(f"   Average per Bus:       ₹{avg_profit:,.2f}")
        self.stdout.write(f"   Total Passengers:      {total_passengers:,}")
        self.stdout.write(f"   Highest Earner:        {bus_profits[0]['bus'].number_plate} (₹{bus_profits[0]['profit']:,.2f})")
        self.stdout.write(f"   Lowest Earner:         {bus_profits[-1]['bus'].number_plate} (₹{bus_profits[-1]['profit']:,.2f})")
        self.stdout.write(f"   Profit Difference:     ₹{bus_profits[0]['profit'] - bus_profits[-1]['profit']:,.2f}")
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Profit calculation complete!"))
        self.stdout.write(f"\n💡 Next steps:")
        self.stdout.write(f"   1. View dashboard: http://localhost:8000/zonal-admin/weekly-profit/")
        self.stdout.write(f"   2. Results saved to WeeklyBusPerformance table")
        self.stdout.write("")
    
    def calculate_bus_profit(self, bus, week_start, week_end):
        """Calculate profit for a single bus for the week"""
        
        # Constants
        FARE_PER_PASSENGER = 25  # ₹25 per passenger
        FUEL_PRICE_PER_LITER = 100  # ₹100 per liter
        
        # Get all schedules
        schedules = Schedule.objects.filter(
            bus=bus,
            date__gte=week_start,
            date__lte=week_end
        ).select_related('route')
        
        # 1. Count trips
        total_trips = schedules.count()
        
        # 2. Count passengers (total_seats - available_seats)
        total_passengers = sum(
            s.total_seats - s.available_seats 
            for s in schedules
        )
        
        # 3. Calculate revenue
        total_revenue = Decimal(total_passengers * FARE_PER_PASSENGER)
        
        # 4. Calculate total distance
        total_distance = sum(s.route.total_distance for s in schedules)
        
        # 5. Calculate fuel cost
        if bus.mileage and bus.mileage > 0:
            fuel_consumed = total_distance / bus.mileage  # liters
        else:
            fuel_consumed = total_distance / 5  # Default 5 km/L
        
        total_fuel_cost = Decimal(fuel_consumed * FUEL_PRICE_PER_LITER)
        
        # 6. Calculate profit
        total_profit = total_revenue - total_fuel_cost
        
        return {
            'bus': bus,
            'trips': total_trips,
            'passengers': total_passengers,
            'distance': total_distance,
            'revenue': total_revenue,
            'fuel_cost': total_fuel_cost,
            'profit': total_profit,
        }