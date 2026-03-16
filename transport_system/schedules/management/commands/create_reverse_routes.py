"""
Create Reverse Routes
For every existing route A→F, creates a return route F→A
with stops in reverse sequence.

Usage:
    python manage.py create_reverse_routes
    python manage.py create_reverse_routes --dry-run  (preview only)
"""

from django.core.management.base import BaseCommand
from routes.models import Route, Stop


class Command(BaseCommand):
    help = 'Create reverse routes for all existing one-way routes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what will be created without saving'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING("\n🔍 DRY RUN — nothing will be saved\n"))
        else:
            self.stdout.write("\n🔄 Creating Reverse Routes\n")

        # Get all routes that don't already have a reverse
        # We identify reverse routes by checking if number ends with 'R'
        forward_routes = Route.objects.exclude(
            number__endswith='R'
        ).prefetch_related('stops').order_by('number')

        if not forward_routes.exists():
            self.stdout.write(self.style.ERROR('No forward routes found.'))
            return

        self.stdout.write(f"Found {forward_routes.count()} forward routes\n")

        created = 0
        skipped = 0

        for route in forward_routes:
            reverse_number = f"{route.number}R"

            # Skip if reverse already exists
            if Route.objects.filter(number=reverse_number).exists():
                self.stdout.write(
                    f"   ⏭️  Skipping {route.number} → {reverse_number} already exists"
                )
                skipped += 1
                continue

            stops = list(route.stops.order_by('sequence'))

            if len(stops) < 2:
                self.stdout.write(
                    f"   ⚠️  Skipping {route.number} — less than 2 stops"
                )
                skipped += 1
                continue

            self.stdout.write(
                f"   ✅ {route.number}: {route.origin} → {route.destination}  "
                f"becomes  {reverse_number}: {route.destination} → {route.origin}"
            )

            if not dry_run:
                # Create reverse route
                reverse_route = Route.objects.create(
                    number=reverse_number,
                    name=f"{route.name} (Return)",
                    description=f"Return route for {route.number}",
                    origin=route.destination,        # ✅ swapped
                    destination=route.origin,        # ✅ swapped
                    total_distance=route.total_distance,
                    duration=route.duration,
                    turnaround_time=route.turnaround_time,
                    buffer_time=route.buffer_time,
                    zone=route.zone,
                )

                # Create stops in reverse order
                total_stops = len(stops)
                for new_seq, stop in enumerate(reversed(stops), start=1):
                    # Distance from new origin = total_distance - old distance
                    new_distance = route.total_distance - stop.distance_from_origin

                    Stop.objects.create(
                        route=reverse_route,
                        name=stop.name,
                        sequence=new_seq,
                        distance_from_origin=new_distance,
                        is_limited_stop=stop.is_limited_stop,
                    )

                created += 1

        self.stdout.write("\n" + "="*50)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN complete. Would create {forward_routes.count() - skipped} reverse routes.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"✅ Created {created} reverse routes, skipped {skipped}")
            )
        self.stdout.write("="*50 + "\n")