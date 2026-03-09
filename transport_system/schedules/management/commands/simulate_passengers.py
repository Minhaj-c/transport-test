"""
Simulate Passenger Data for Testing

This adds realistic passenger data to existing schedules
so you can test the profit calculation and fair rotation system.

Usage:
    python manage.py simulate_passengers --week-start=2026-03-03
    python manage.py simulate_passengers --week-start=2026-03-03 --reset-first
"""

from django.core.management.base import BaseCommand
from datetime import date, timedelta
import random

from schedules.models import Schedule


class Command(BaseCommand):
    help = 'Add simulated passenger data to existing schedules for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--week-start',
            type=str,
            required=True,
            help='Week start date (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--reset-first',
            action='store_true',
            help='Reset all passengers to 0 before simulating'
        )

    def handle(self, *args, **options):
        week_start = date.fromisoformat(options['week_start'])
        week_end = week_start + timedelta(days=6)
        
        self.stdout.write("\n" + "="*70)
        self.stdout.write("🎲 SIMULATING PASSENGER DATA".center(70))
        self.stdout.write("="*70)
        self.stdout.write(f"\n📅 Week: {week_start} to {week_end}")
        self.stdout.write("⚠️  This is for TESTING only - production uses real driver data\n")
        
        # Get all schedules for this week
        schedules = Schedule.objects.filter(
            date__gte=week_start,
            date__lte=week_end
        ).select_related('route', 'bus').order_by('date', 'departure_time')
        
        if not schedules.exists():
            self.stdout.write(self.style.ERROR('❌ No schedules found for this week!'))
            self.stdout.write('💡 Create schedules first:\n')
            self.stdout.write(f'   python manage.py create_smart_schedules --week-start={week_start}\n')
            return
        
        total = schedules.count()
        self.stdout.write(f"📊 Found {total} schedules\n")
        
        # Reset if requested
        if options['reset_first']:
            self.stdout.write("🔄 Resetting all passengers to 0...")
            schedules.update(current_passengers=0, available_seats=0)
            for s in schedules:
                s.available_seats = s.total_seats
                s.save(update_fields=['available_seats'])
            self.stdout.write(self.style.SUCCESS("✅ Reset complete\n"))
        
        # Simulate passengers
        self.stdout.write("🎲 Simulating passenger data...\n")
        
        updated = 0
        total_passengers = 0
        
        # Get unique routes and rank them by number (lower = better)
        routes = list(schedules.values_list('route_id', flat=True).distinct())
        route_rank = {route_id: idx for idx, route_id in enumerate(sorted(routes))}
        
        for schedule in schedules:
            # Calculate base occupancy
            base_occupancy = 0.65  # 65% average
            
            # Route quality multiplier (lower route number = better = more passengers)
            route_quality = 1.5 - (route_rank.get(schedule.route_id, 0) * 0.1)
            route_quality = max(0.7, min(1.5, route_quality))
            
            # Time of day multiplier
            hour = schedule.departure_time.hour
            if 6 <= hour <= 8 or 17 <= hour <= 19:  # Peak hours
                time_multiplier = 1.2
            elif 12 <= hour <= 14:  # Lunch
                time_multiplier = 1.0
            else:  # Off-peak
                time_multiplier = 0.8
            
            # Day of week multiplier
            weekday = schedule.date.weekday()
            if weekday in [5, 6]:  # Weekend
                day_multiplier = 0.7
            else:  # Weekday
                day_multiplier = 1.0
            
            # Calculate passengers
            target_occupancy = base_occupancy * route_quality * time_multiplier * day_multiplier
            target_occupancy = max(0.3, min(0.95, target_occupancy))  # Between 30% and 95%
            
            # Add randomness
            variance = random.uniform(0.85, 1.15)
            final_occupancy = target_occupancy * variance
            
            passengers = int(schedule.total_seats * final_occupancy)
            passengers = max(1, min(passengers, schedule.total_seats))  # At least 1, max capacity
            
            # Update schedule
            schedule.current_passengers = passengers
            schedule.available_seats = schedule.total_seats - passengers
            schedule.save(update_fields=['current_passengers', 'available_seats'])
            
            updated += 1
            total_passengers += passengers
        
        # Summary
        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS("✅ SIMULATION COMPLETE"))
        self.stdout.write("="*70 + "\n")
        
        self.stdout.write(f"📊 Statistics:")
        self.stdout.write(f"   • Updated {updated} schedules")
        self.stdout.write(f"   • Total passengers: {total_passengers:,}")
        self.stdout.write(f"   • Average per trip: {total_passengers // updated if updated else 0}")
        
        avg_occupancy = (total_passengers / (updated * 40)) * 100 if updated else 0
        self.stdout.write(f"   • Average occupancy: {avg_occupancy:.1f}%\n")
        
        self.stdout.write("💡 Next Steps:")
        self.stdout.write(f"   1. Calculate profits:")
        self.stdout.write(f"      python manage.py calculate_weekly_profits --week-start={week_start}\n")
        self.stdout.write(f"   2. View dashboard:")
        self.stdout.write(f"      http://localhost:8000/zonal-admin/weekly-profit/\n")
        self.stdout.write(f"   3. Generate next week with fair rotation:")
        next_week = week_start + timedelta(days=7)
        self.stdout.write(f"      python manage.py create_smart_schedules --week-start={next_week}\n")