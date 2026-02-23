# schedules/management/commands/reset_database.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Clear ALL data from database (keep structure)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Actually delete the data (required for safety)',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(self.style.WARNING(
                '\n⚠️  This will DELETE ALL DATA from your database!\n'
                'Run with --confirm flag to proceed:\n'
                '  python manage.py reset_database --confirm\n'
            ))
            return

        self.stdout.write('\n🗑️  CLEARING ALL DATA...\n')

        # Import all models
        from schedules.models import (
            Schedule, Bus, BusSchedule, 
            WeeklyBusPerformance, RouteProfitability,
            BusRouteAssignment, SpareBusSchedule, SpareDispatchRequest
        )
        from routes.models import Route, Stop
        from preinforms.models import PreInform
        from demand.models import DemandAlert
        from zones.models import Zone

        # Delete in correct order (respecting foreign keys)
        
        # 1. Schedules and related
        count = Schedule.objects.count()
        Schedule.objects.all().delete()
        self.stdout.write(f'  ✅ Deleted {count} schedules')

        count = BusSchedule.objects.count()
        BusSchedule.objects.all().delete()
        self.stdout.write(f'  ✅ Deleted {count} bus assignments')

        count = WeeklyBusPerformance.objects.count()
        WeeklyBusPerformance.objects.all().delete()
        self.stdout.write(f'  ✅ Deleted {count} performance records')

        count = RouteProfitability.objects.count()
        RouteProfitability.objects.all().delete()
        self.stdout.write(f'  ✅ Deleted {count} route profitability records')

        count = BusRouteAssignment.objects.count()
        BusRouteAssignment.objects.all().delete()
        self.stdout.write(f'  ✅ Deleted {count} route assignments')

        count = SpareBusSchedule.objects.count()
        SpareBusSchedule.objects.all().delete()
        self.stdout.write(f'  ✅ Deleted {count} spare bus schedules')

        count = SpareDispatchRequest.objects.count()
        SpareDispatchRequest.objects.all().delete()
        self.stdout.write(f'  ✅ Deleted {count} spare dispatch requests')

        # 2. PreInforms
        count = PreInform.objects.count()
        PreInform.objects.all().delete()
        self.stdout.write(f'  ✅ Deleted {count} pre-informs')

        # 3. Demand Alerts
        count = DemandAlert.objects.count()
        DemandAlert.objects.all().delete()
        self.stdout.write(f'  ✅ Deleted {count} demand alerts')

        # 4. Routes and Stops
        count = Stop.objects.count()
        Stop.objects.all().delete()
        self.stdout.write(f'  ✅ Deleted {count} stops')

        count = Route.objects.count()
        Route.objects.all().delete()
        self.stdout.write(f'  ✅ Deleted {count} routes')

        # 5. Buses
        count = Bus.objects.count()
        Bus.objects.all().delete()
        self.stdout.write(f'  ✅ Deleted {count} buses')

        # 6. Zones
        count = Zone.objects.count()
        Zone.objects.all().delete()
        self.stdout.write(f'  ✅ Deleted {count} zones')

        # 7. Users (except superusers)
        non_admin_users = User.objects.filter(is_superuser=False)
        count = non_admin_users.count()
        non_admin_users.delete()
        self.stdout.write(f'  ✅ Deleted {count} users (kept superusers)')

        self.stdout.write(self.style.SUCCESS(
            '\n✅ Database cleared! Structure intact.\n'
        ))
        self.stdout.write('💡 Now you can add fresh data:\n')
        self.stdout.write('   - Add zones via admin\n')
        self.stdout.write('   - Add routes and stops\n')
        self.stdout.write('   - Add buses\n')
        self.stdout.write('   - Add drivers\n')
        self.stdout.write('   - Generate schedules\n')