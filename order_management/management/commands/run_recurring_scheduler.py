import time
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone

class Command(BaseCommand):
    help = 'Runs generate_recurring_orders once per day'

    def add_arguments(self, parser):
        parser.add_argument('--interval', type=int, default=86400)

    def handle(self, *args, **options):
        interval = options['interval']
        self.stdout.write(f"Scheduler started, interval {interval}s")
        while True:
            self.stdout.write(f"Running generate_recurring_orders at {timezone.now()}")
            try:
                call_command('generate_recurring_orders')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error: {e}"))
            self.stdout.write(f"Sleeping for {interval} seconds...")
            time.sleep(interval)