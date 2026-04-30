from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from order_management.models import RecurringOrderInstance, OrderItem
from shopping_cart.models import CartItem
from product.models import Product
from django.db.models import Sum

class Command(BaseCommand):
    help = 'Check stock for future recurring order instances and mark alerts'

    def handle(self, *args, **options):
        today = timezone.now().date()
        future_instances = RecurringOrderInstance.objects.filter(
            scheduled_date__gte=today,
            scheduled_date__lte=today + timedelta(days=14),
            status='generated'
        ).select_related('order', 'template__customer')

        alert_count = 0
        for instance in future_instances:
            has_issue = self.check_instance_stock(instance)
            if has_issue:
                if not instance.last_stock_alert_sent or (timezone.now() - instance.last_stock_alert_sent).days >= 1:
                    instance.last_stock_alert_sent = timezone.now()
                    instance.save(update_fields=['last_stock_alert_sent'])
                    alert_count += 1
                    self.stdout.write(self.style.WARNING(f"Alert set for instance {instance.instance_id} (order #{instance.order.order_id})"))
            else:
                if instance.last_stock_alert_sent:
                    instance.last_stock_alert_sent = None
                    instance.save(update_fields=['last_stock_alert_sent'])

        self.stdout.write(self.style.SUCCESS(f"Stock check completed. Alerts set: {alert_count}"))

    def check_instance_stock(self, instance):
        order = instance.order
        for suborder in order.suborders.all():
            for order_item in suborder.items.all():
                product = order_item.product
                requested_qty = order_item.quantity
                reserved_by_others = CartItem.objects.filter(
                    product=product,
                    reserved_until__gt=timezone.now()
                ).aggregate(total=Sum('quantity'))['total'] or 0
                available = product.stock_quantity - reserved_by_others

                if not product.availability_status or available < requested_qty:
                    return True
        return False