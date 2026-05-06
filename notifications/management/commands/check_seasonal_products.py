from django.core.management.base import BaseCommand
from notifications.seasonal_notify import notify_producers_upcoming_seasonal_products

class Command(BaseCommand):
    help = 'Check for upcoming seasonal products and notify producers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days before season start to notify (default: 7)'
        )

    def handle(self, *args, **options):
        days = options['days']
        count = notify_producers_upcoming_seasonal_products(days_before=days)
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully sent {count} seasonal product notifications for {days} days ahead'
            )
        )