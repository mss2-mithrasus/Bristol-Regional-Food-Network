
from django.core.management.base import BaseCommand
from django.utils import timezone
from shopping_cart.models import CartItem
from shopping_cart.views import check_and_notify_stock_available

class Command(BaseCommand):
    help = 'Release expired cart reservations and notify waiting customers'

    def handle(self, *args, **options):
        self.stdout.write(f"[{timezone.now()}] Checking for expired cart reservations...")
        
        now = timezone.now()
        
        # Find all expired cart items
        expired_items = CartItem.objects.filter(
            reserved_until__lt=now
        ).select_related('product')
        
        expired_count = expired_items.count()
        
        if expired_count == 0:
            self.stdout.write(self.style.SUCCESS("No expired items found"))
            return
        
        self.stdout.write(f"Found {expired_count} expired items")
        
        # Group by product to check stock availability after deletion
        products_to_check = set()
        for item in expired_items:
            products_to_check.add(item.product)
            self.stdout.write(f"  Expired: {item.product.name} x{item.quantity} (reserved until {item.reserved_until})")
        
        # Delete all expired items
        expired_items.delete()
        self.stdout.write(f"Deleted {expired_count} expired items")
        
        # Check each product for stock availability and notify waiting customers
        notifications_sent = 0
        for product in products_to_check:
            notified = check_and_notify_stock_available(product)
            if notified > 0:
                notifications_sent += notified
                self.stdout.write(self.style.SUCCESS(f"   Notified {notified} customers about {product.name}"))
        
        self.stdout.write(self.style.SUCCESS(
            f"Done! Processed {expired_count} expired items, sent {notifications_sent} notifications"
        ))