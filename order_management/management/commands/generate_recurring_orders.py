from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from order_management.models import RecurringTemplate, RecurringOrderInstance
from order_management.models import Order, SubOrder, OrderItem
from product.models import Product
from decimal import Decimal

class Command(BaseCommand):
    help = 'Generate recurring orders for the next few cycles (4 weeks for weekly, etc.)'

    def handle(self, *args, **options):
        today = timezone.now().date()
        templates = RecurringTemplate.objects.filter(is_active=True)
        created = 0

        for template in templates:
            # Determine how many future deliveries to generate
            if template.recurrence == 'weekly':
                max_weeks = 4  # Show 4 weeks ahead
            elif template.recurrence == 'fortnightly':
                max_weeks = 2  # Show 2 deliveries (4 weeks total)
            else:  # monthly
                max_weeks = 1  # Show 1 delivery (4 weeks ahead)

            # Compute the first delivery date on or after today
            next_date = self.get_next_delivery_date(template, today)
            if not next_date or (template.end_date and next_date > template.end_date):
                continue

            # Generate up to max_weeks deliveries (by adding recurrence intervals)
            current = next_date
            count = 0
            while count < max_weeks and (not template.end_date or current <= template.end_date):
                # Check if an instance already exists for this date
                if not RecurringOrderInstance.objects.filter(template=template, scheduled_date=current).exists():
                    try:
                        self.create_order_from_template(template, current)
                        created += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Failed for template {template.template_id} on {current}: {e}"))
                # Move to next delivery date
                if template.recurrence == 'weekly':
                    current += timedelta(weeks=1)
                elif template.recurrence == 'fortnightly':
                    current += timedelta(weeks=2)
                else:  # monthly
                    current += timedelta(days=28)  # approximate 4 weeks
                count += 1

        self.stdout.write(self.style.SUCCESS(f"Generated {created} recurring orders"))

    def get_next_delivery_date(self, template, reference_date):
        if reference_date < template.start_date:
            reference_date = template.start_date

        if template.recurrence == 'weekly':
            delta = timedelta(weeks=1)
        elif template.recurrence == 'fortnightly':
            delta = timedelta(weeks=2)
        else:
            delta = timedelta(days=28)

        current = template.start_date
        while current < reference_date:
            current += delta
        return current

    def create_order_from_template(self, template, delivery_date):
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
            order_status=Order.OrderStatus.PENDING
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