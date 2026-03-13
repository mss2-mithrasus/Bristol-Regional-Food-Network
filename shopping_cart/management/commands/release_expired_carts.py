from django.core.management.base import BaseCommand
from django.utils import timezone
from shopping_cart.models import CartItem

class Command(BaseCommand):
    help = 'Release expired cart reservations'

    def handle(self, *args, **options):
        expired = CartItem.objects.filter(
            reserved_until__lt=timezone.now()
        )
        count = expired.count()
        expired.delete()
        self.stdout.write(
            self.style.SUCCESS(f'Released {count} expired cart reservations')
        )