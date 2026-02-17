# schedules/management/commands/clear_all_schedules.py

from django.core.management.base import BaseCommand
from schedules.models import Schedule, WeeklyBusPerformance, SpareBusSchedule, BusRouteAssignment


class Command(BaseCommand):
    help = 'Clear ALL schedule data and start fresh'

    def handle(self, *args, **options):
        self.stdout.write("\n🗑️  Clearing all schedule data...\n")

        # Count before deleting
        s_count  = Schedule.objects.count()
        p_count  = WeeklyBusPerformance.objects.count()
        sp_count = SpareBusSchedule.objects.count()

        # Delete everything
        Schedule.objects.all().delete()
        WeeklyBusPerformance.objects.all().delete()
        SpareBusSchedule.objects.all().delete()

        # BusRouteAssignment may not exist yet - safe delete
        try:
            BusRouteAssignment.objects.all().delete()
        except Exception:
            pass

        self.stdout.write(self.style.SUCCESS(f"✅ Deleted {s_count} schedules"))
        self.stdout.write(self.style.SUCCESS(f"✅ Deleted {p_count} profit records"))
        self.stdout.write(self.style.SUCCESS(f"✅ Deleted {sp_count} spare bus entries"))
        self.stdout.write(self.style.SUCCESS("\n✅ Database is clean! Ready to start fresh.\n"))
        self.stdout.write("💡 Now run:")
        self.stdout.write("   python manage.py create_balanced_schedules --week-start=2026-03-02\n")