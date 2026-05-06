from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from user_accounts.models import ProducerAccount
from order_management.models import SubOrder, OrderStatusHistory
from producers.models import SettlementReport, ProducerSettlementOrder
import time
from django.db.models import Subquery, OuterRef

class Command(BaseCommand):
    help = "Auto-generate weekly settlements for all producers"

    def handle(self, *args, **options):
        self.stdout.write("Settlement scheduler started. Checking every 6 hours...")
        while True:
            self._generate_settlements()
            time.sleep(6 * 60 * 60)

    def _generate_settlements(self):
        today = timezone.now().date()

        days_since_sunday = (today.weekday() + 1) % 7
        if days_since_sunday == 0:
            week_end = today - timedelta(days=7)
        else:
            week_end = today - timedelta(days=days_since_sunday)

        week_start = week_end - timedelta(days=6)

        self.stdout.write(f"Checking settlements for week {week_start} to {week_end}")

        producers = ProducerAccount.objects.all()

        for producer in producers:
            existing = SettlementReport.objects.filter(
                producer=producer,
                week_start=week_start,
                week_end=week_end
            ).first()

            if existing:
                existing.settlement_orders.all().delete()
                existing.delete()

            delivered_date_sq = (
                OrderStatusHistory.objects
                .filter(suborder=OuterRef('pk'), new_status='Delivered')
                .order_by('-order_status_changed_at')
                .values('order_status_changed_at')[:1]
            )

            suborders = (
                SubOrder.objects
                .filter(producer=producer, status="Delivered")
                .annotate(actual_delivered_date=Subquery(delivered_date_sq))
                .filter(actual_delivered_date__date__range=[week_start, week_end])
                .select_related("order")
            )

            if not suborders.exists():
                continue

            total_value = Decimal("0.00")
            total_commission = Decimal("0.00")
            total_payout = Decimal("0.00")
            order_list = []

            for sub in suborders:
                order_value = Decimal(sub.subtotal or 0)
                commission = (order_value * Decimal("0.05")).quantize(Decimal("0.01"))
                payout = (order_value * Decimal("0.95")).quantize(Decimal("0.01"))
                total_value += order_value
                total_commission += commission
                total_payout += payout
                order_list.append({
                    "order_id": sub.order.order_id,
                    "order_value": order_value,
                    "commission": commission,
                    "payout": payout,
                })

            with transaction.atomic():
                settlement = SettlementReport.objects.create(
                    producer=producer,
                    week_start=week_start,
                    week_end=week_end,
                    total_order_value=total_value,
                    commission_amount=total_commission,
                    payout_amount=total_payout,
                    payment_status="Processed",
                )
                ProducerSettlementOrder.objects.bulk_create([
                    ProducerSettlementOrder(
                        settlement_report=settlement,
                        order_id=o["order_id"],
                        order_value=o["order_value"],
                        commission_amount=o["commission"],
                        producer_payout=o["payout"],
                    ) for o in order_list
                ])

            self.stdout.write(self.style.SUCCESS(
                f"Settlement created for {producer.business_name} - Â£{total_payout}"
            ))

        self.stdout.write(self.style.SUCCESS("Settlement check complete."))