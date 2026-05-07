from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from dateutil.relativedelta import relativedelta   # ADDED: for calendar‑aware months
from order_management.models import RecurringTemplate, RecurringOrderInstance, Order, SubOrder, OrderItem
from product.models import Product
from decimal import Decimal

class Command(BaseCommand):
    help = 'Generate recurring orders for the next few cycles'

    def handle(self, *args, **options):
        today = timezone.now().date()
        # NEW: only generate orders up to 6 months ahead (prevents infinite future orders)
        horizon = today + relativedelta(months=6)
        templates = RecurringTemplate.objects.filter(is_active=True)
        created = 0

        for template in templates:
            # NEW: skip templates whose start date is already beyond horizon
            if template.start_date > horizon:
                continue

            # Determine how many future deliveries to generate
            # (weekly = 4 deliveries, fortnightly = 2, monthly = 1)
            if template.recurrence == 'weekly':
                max_deliveries = 4
                delta = relativedelta(weeks=1)          # CHANGED: use relativedelta for consistency
            elif template.recurrence == 'fortnightly':
                max_deliveries = 2
                delta = relativedelta(weeks=2)
            else:  # monthly
                max_deliveries = 2
                # CHANGE: from timedelta(days=28) to relativedelta(months=1)
                # This makes monthly orders follow calendar months (28-31 days) correctly.
                delta = relativedelta(months=1)

            # Compute the first delivery date on or after today
            next_date = self.get_next_delivery_date(template, today, delta)
            if not next_date or next_date > horizon:
                continue

            current = next_date
            deliveries_made = 0
            while deliveries_made < max_deliveries and current <= horizon:
                if not template.end_date or current <= template.end_date:
                    # Use get_or_create? We keep simple existence check to avoid duplicates
                    if not RecurringOrderInstance.objects.filter(template=template, scheduled_date=current).exists():
                        try:
                            self.create_order_from_template(template, current)
                            created += 1
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"Failed for template {template.template_id} on {current}: {e}"))
                # Move to next delivery date using the same delta (now calendar‑aware for monthly)
                current += delta
                deliveries_made += 1

        self.stdout.write(self.style.SUCCESS(f"Generated {created} recurring orders"))

    # CHANGED: get_next_delivery_date now accepts delta (the recurrence interval) as argument
    def get_next_delivery_date(self, template, reference_date, delta):
        current = template.start_date
        while current < reference_date:
            current += delta
        return current

    def create_order_from_template(self, template, delivery_date):
        # (unchanged – creates Order, SubOrder, OrderItem)
        customer = template.customer
        street = ''
        postcode = ''
        if hasattr(customer, 'address') and customer.address:
            street = customer.address.address_line or ''
            postcode = customer.address.postcode or ''
        else:
            raise ValueError(f"Customer {customer.user.email} has no address")

        producer_items = {}
        for item_data in template.items:
            product = Product.objects.get(product_id=item_data['product_id'])
            producer_id = product.producer_id
            producer_items.setdefault(producer_id, []).append({
                'product': product,
                'quantity': item_data['quantity'],
                'price': product.price
            })

        order = Order.objects.create(
            customer=customer,
            total_amount=0,
            commission_amount=0,
            delivery_address=street,
            delivery_postcode=postcode,
            order_status=Order.OrderStatus.PENDING,
            fulfillment_method='delivery'
        )

        total_order = Decimal('0')
        for producer_id, items in producer_items.items():
            subtotal = sum(Decimal(str(i['price'])) * i['quantity'] for i in items)
            commission_amount = (subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
            payout = subtotal - commission_amount

            suborder = SubOrder.objects.create(
                order=order,
                producer_id=producer_id,
                delivery_date=delivery_date,
                subtotal=subtotal,
                payout_amount=payout,
                status=SubOrder.SubOrderStatus.PENDING
            )

            for i in items:
                OrderItem.objects.create(
                    suborder=suborder,
                    product=i['product'],
                    quantity=i['quantity'],
                    price_at_purchase=i['price'],
                    original_price_at_purchase=i['price']
                )
            total_order += subtotal

        order.total_amount = total_order
        order.commission_amount = total_order * Decimal('0.05')
        order.save()

        RecurringOrderInstance.objects.create(
            template=template,
            order=order,
            scheduled_date=delivery_date,
            status='generated'
        )