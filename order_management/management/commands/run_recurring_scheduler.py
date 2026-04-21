import time
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone

class Command(BaseCommand):
    help = 'Runs generate_recurring_orders once per day (or custom interval)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=86400,
            help='Interval in seconds between runs (default 86400 = 1 day)'
        )

    def handle(self, *args, **options):
        interval = options['interval']
        self.stdout.write(f"Recurring order scheduler started. Will run every {interval} seconds.")
        while True:
            self.stdout.write(f"Running generate_recurring_orders at {timezone.now()}")
            call_command('generate_recurring_orders')
            self.stdout.write(f"Sleeping for {interval} seconds until next run...")
            time.sleep(interval)