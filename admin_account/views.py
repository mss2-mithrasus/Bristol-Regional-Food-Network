import hashlib 
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.views import View
from django.db.models import Sum, Count, F
from django.db.models.functions import TruncDate
from user_accounts.permissions import IsAdmin
from product.models import ReviewProduct
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated

from rest_framework.views import APIView
from rest_framework.response import Response

from user_accounts.models import (
    CustomerAccount,
    ProducerAccount,
    User,
    DeletionAudit,
    FailedLoginAttempt
)
# Admin Financial Reports 
from django.http import JsonResponse, HttpResponse
from django.utils.dateparse import parse_date
from django.db.models import Sum, Count
from datetime import datetime, timedelta
from decimal import Decimal

from order_management.models import Order, SubOrder, OrderItem
from payments.models import PaymentTransaction
from django.views.decorators.http import require_GET
from decimal import Decimal, ROUND_HALF_UP


# Check if user is admin
def is_admin(user):
    return user.is_authenticated and user.role == "admin"

# Money
def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

# Admin home page 
@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin), name="dispatch")
class AdminHomePageView(View):
    def get(self, request):
        return render(request, "admin_home_page.html")


@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin), name="dispatch")
class AdminPendingPageView(View):
    def get(self, request):
        return render(request, "admin_pending.html")

@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin), name="dispatch")
class AdminFailedLoginsPageView(View):
    def get(self, request):
        return render(request, "admin_failed_logins.html")


@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin), name="dispatch")
class AdminDeletedAccountsPageView(View):
    def get(self, request):
        return render(request, "admin_deleted_accounts.html")


@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin), name="dispatch")
class AdminFinancialReportsPageView(View):
    def get(self, request):
        return render(request, "admin_financial_reports.html")

@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin), name="dispatch")
class AdminAnalyticsPageView(View):
    def get(self, request):
        return render(request, "admin_analytics.html")


# Show pending accounts
class PendingAccountsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        customers = CustomerAccount.objects.filter(account_verified=False).select_related(
            "user", "person"
        ).prefetch_related("communitygroup", "restaurant")
        producers = ProducerAccount.objects.filter(account_verified=False).select_related(
            "user", "contact_person"
        )

        customer_list = []

        for c in customers:
            base = {
                "user_id": c.user.id,
                "email": c.user.email,
                "account_type": c.account_type,
            }

            if c.account_type == "normal":
                person = c.person
                base.update({
                    "name": f"{person.first_name} {person.last_name}" if person else "N/A",
                    "phone": person.phone if person else None,
                    "organisation_name": None,
                })

            elif c.account_type == "community":
                cg = getattr(c, "communitygroup", None)
                base.update({
                    "name": cg.organisation_name if cg else "N/A",
                    "organisation_name": cg.organisation_name if cg else None,
                    "phone": cg.phone if cg else None,
                })

            elif c.account_type == "restaurant":
                r = getattr(c, "restaurant", None)
                base.update({
                    "name": r.organisation_name if r else "N/A",
                    "organisation_name": r.organisation_name if r else None,
                    "phone": r.phone if r else None,
                })

            customer_list.append(base)

        producer_list = []
        for p in producers:
            person = p.contact_person
            producer_list.append({
                "user_id": p.user.id,
                "email": p.user.email,
                "business_name": p.business_name,
                "name": f"{person.first_name} {person.last_name}" if person else "N/A",
                "phone": person.phone if person else None,
            })

        return Response({
            "customers": customer_list,
            "producers": producer_list
        })
# Approve account
class ApproveAccountView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        user_id = request.data.get("user_id")
        role = request.data.get("role")

        if role == "producer":
            ProducerAccount.objects.filter(user_id=user_id).update(account_verified=True)
        else:
            CustomerAccount.objects.filter(user_id=user_id).update(account_verified=True)

        return Response({"message": "Account approved"})


# Reject account
class RejectAccountView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        user_id = request.data.get("user_id")
        User.objects.filter(id=user_id).delete()
        return Response({"message": "Account rejected"})

# ADDED (10-03-26)
# Deleted account history
class DeletedAccountsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        audits = DeletionAudit.objects.all().order_by("-deleted_at")

        results = []
        for entry in audits:
            results.append({
                "hashed_user_identifier": entry.hashed_user_identifier,
                "role": entry.role,
                "reason": entry.reason,
                "deleted_at": entry.deleted_at,
            })

        return Response(results)
    
# Failed login attempts history
class FailedLoginAttemptsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        attempts = FailedLoginAttempt.objects.all().order_by("-timestamp")

        results = []
        for attempt in attempts:
            results.append({
                "email": attempt.email,
                "ip_address": attempt.ip_address,
                "user_agent": attempt.user_agent,
                "timestamp": attempt.timestamp,
            })

        return Response(results)

# ADDED 19/03/2026
# Admin financial reports 
@require_GET
def FinancialReportsMeta(request):
    """
    Returns earliest and latest PAID order dates.
    Used to auto-fill the date pickers on the financial reports page.
    """
    paid_order_ids = PaymentTransaction.objects.filter(
        payment_status=PaymentTransaction.PaymentStatus.SUCCEEDED
    ).values_list("order_id", flat=True)

    try:
        min_date = Order.objects.filter(order_id__in=paid_order_ids).earliest("created_at").created_at.date()
        max_date = Order.objects.filter(order_id__in=paid_order_ids).latest("created_at").created_at.date()
    except Order.DoesNotExist:
        return JsonResponse({
            "min_date": None,
            "max_date": None
        })

    return JsonResponse({
        "min_date": min_date,
        "max_date": max_date
    })

@require_GET 
def FinancialReports(request):
    """
    Admin financial report:
    - Filters by date range
    - Includes only PAID orders
    - Returns totals + per-order breakdown
    """

    start_str = request.GET.get("start")
    end_str = request.GET.get("end")

    if not start_str or not end_str:
        today = datetime.today().date()
        start_date = today - timedelta(days=14)
        end_date = today
    else:
        start_date = parse_date(start_str)
        end_date = parse_date(end_str)

    paid_order_ids = PaymentTransaction.objects.filter(
        payment_status=PaymentTransaction.PaymentStatus.SUCCEEDED
    ).values_list("order_id", flat=True)

    # orders_qs = (
    #     Order.objects
    #     .filter(
    #         created_at__date__gte=start_date,
    #         created_at__date__lte=end_date,
    #         order_id__in=paid_order_ids,
    #     )
    #     .select_related("customer")
    #     .prefetch_related("suborders__producer")
    # )
    orders_qs = (
        Order.objects
        .filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            order_id__in=paid_order_ids,
        )
        .select_related("customer")
        .prefetch_related("suborders__producer", "suborders__items__product")
    )

    aggregates = orders_qs.aggregate(
        total_order_value=Sum("total_amount"),
        order_count=Count("order_id"),
    )

    total_order_value = money(aggregates["total_order_value"] or Decimal("0.00"))

    # Calculate from total price, not summed producer rounded values
    total_commission = money(total_order_value * Decimal("0.05"))
    total_producer_payments = money(total_order_value * Decimal("0.95"))

    orders_data = []
    for order in orders_qs:
        producer_rows = []
        for s in order.suborders.all():
            subtotal = Decimal(str(s.subtotal))

            commission = (subtotal * Decimal("0.05")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            payout = (subtotal * Decimal("0.95")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            item_rows = []

            for item in s.items.all():
                original_price = getattr(item, "original_price_at_purchase", None) or item.price_at_purchase
                discounted_price = item.price_at_purchase

                original_line_total = (Decimal(str(original_price)) * item.quantity).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                discounted_line_total = (Decimal(str(discounted_price)) * item.quantity).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

                item_rows.append({
                    "product_name": item.product.name,
                    "quantity": item.quantity,
                    "original_unit_price": str(original_price),
                    "discounted_unit_price": str(discounted_price),
                    "original_line_total": str(original_line_total),
                    "discounted_line_total": str(discounted_line_total),
                    "has_surplus_discount": Decimal(str(original_price)) != Decimal(str(discounted_price)),
                })

            producer_rows.append({
                "producer": str(s.producer),
                "subtotal": str(subtotal),
                "commission": str(commission),
                "payout": str(payout),
                "items": item_rows,
            })

    # for order in orders_qs:
    #     producer_rows = []
    #     for s in order.suborders.all():
    #         subtotal = Decimal(str(s.subtotal))

    #         commission = (subtotal * Decimal("0.05")).quantize(
    #             Decimal("0.01"), rounding=ROUND_HALF_UP
    #         )

    #         payout = (subtotal * Decimal("0.95")).quantize(
    #             Decimal("0.01"), rounding=ROUND_HALF_UP
    #         )

    #         producer_rows.append({
    #             "producer": str(s.producer),
    #             "subtotal": str(subtotal),
    #             "commission": str(commission),
    #             "payout": str(payout),
    #         })
        order_total = money(order.total_amount)

        # Calculate from order total
        order_commission = money(order_total * Decimal("0.05"))
        order_payout = money(order_total * Decimal("0.95"))

        orders_data.append({
            "id": order.order_id,
            "customer": str(order.customer),
            "created_at": order.created_at.isoformat(),
            "status": order.order_status,
            "total": str(order_total),
            "commission": str(order_commission),
            "producer_payment": str(order_payout),
            "producers": producer_rows,
        })

    return JsonResponse({
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_order_value": str(total_order_value),
        "total_commission": str(total_commission),
        "total_producer_payments": str(total_producer_payments),
        "order_count": aggregates["order_count"] or 0,
        "orders": orders_data,
    })

# ADDED - 19/03/2026
@require_GET
def FinancialReportsCSV(request):
    """
    CSV export for accounting software.
    """

    start_str = request.GET.get("start")
    end_str = request.GET.get("end")

    if not start_str or not end_str:
        return HttpResponse("start and end query params are required", status=400)

    start_date = parse_date(start_str)
    end_date = parse_date(end_str)

    paid_order_ids = PaymentTransaction.objects.filter(
        payment_status=PaymentTransaction.PaymentStatus.SUCCEEDED
    ).values_list("order_id", flat=True)

    orders_qs = (
        Order.objects
        .filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            order_id__in=paid_order_ids,
        )
        .select_related("customer")
        .prefetch_related("suborders")
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="financial_report_{start_date}_{end_date}.csv"'
    )

    import csv
    writer = csv.writer(response)

    writer.writerow([
        "Order ID",
        "Customer",
        "Created At",
        "Status",
        "Total Amount",
        "Commission Amount (5%)",
        "Producer Payout (95%)",
    ])

    for order in orders_qs:
        order_total = money(order.total_amount)
        commission = money(order_total * Decimal("0.05"))
        payout = money(order_total * Decimal("0.95"))

        writer.writerow([
            order.order_id,
            str(order.customer),
            order.created_at.isoformat(),
            order.order_status,
            str(order_total),
            str(commission),
            str(payout),
        ])

    return response
@require_GET
def AnalyticsMeta(request):
    """
    Returns earliest and latest order dates.
    Used to auto-fill the date pickers on the analytics page.
    """
    try:
        min_date = Order.objects.earliest("created_at").created_at.date()
        max_date = Order.objects.latest("created_at").created_at.date()
    except Order.DoesNotExist:
        return JsonResponse({
            "min_date": None,
            "max_date": None
        })

    return JsonResponse({
        "min_date": min_date,
        "max_date": max_date
    })
def AnalyticsData(request):
    start_str = request.GET.get("start")
    end_str = request.GET.get("end")
    producer_id = request.GET.get("producer")

    filters = {}
    order_filters = {}

    # Date filters
    if start_str:
        filters["order__created_at__date__gte"] = parse_date(start_str)
        order_filters["created_at__date__gte"] = parse_date(start_str)

    if end_str:
        filters["order__created_at__date__lte"] = parse_date(end_str)
        order_filters["created_at__date__lte"] = parse_date(end_str)

    # Producer filter 
    if producer_id:
        filters["producer_id"] = producer_id
        # Producer filter
        order_filters["suborders__producer_id"] = producer_id

    # 1. Payout per producer
    payout = (
        SubOrder.objects.filter(**filters)
        .values("producer__business_name")
        .annotate(total=Sum("payout_amount"))
        .order_by("-total")
    )

    # 2. Commission per producer
    commission = (
        SubOrder.objects.filter(**filters)
        .values("producer__business_name")
        .annotate(total=Sum(F("subtotal") * Decimal("0.05")))
        .order_by("-total")
    )

    # 3. Orders per producer
    orders = (
        SubOrder.objects.filter(**filters)
        .values("producer__business_name")
        .annotate(count=Count("suborder_id"))
        .order_by("-count")
    )

    # 4. Revenue over time 
    revenue = (
        Order.objects.filter(**order_filters)
        .values("created_at__date")
        .annotate(total=Sum("total_amount"))
        .order_by("created_at__date")
    )

    # 5. Commission over time 
    commission_time = (
        Order.objects.filter(**order_filters)
        .values("created_at__date")
        .annotate(total=Sum(F("total_amount") * Decimal("0.05")))
        .order_by("created_at__date")
    )

    producers = list(
        ProducerAccount.objects.values("id", "business_name").order_by("business_name")
    )

    return JsonResponse({
        "payout": list(payout),
        "commission": list(commission),
        "orders": list(orders),
        "revenue": list(revenue),
        "commission_time": list(commission_time),
        "producers": producers,
    })


class PendingReviewsView(APIView):
    permission_classes = [IsAdmin]
    
    def get(self, request):
        reviews = ReviewProduct.objects.filter(review_verified=False).select_related(
            "product",
            "customer__user"
        )
        
        results = []
        
        for r in reviews:
            results.append({
            "review_id": r.review_id,
            "product": r.product.name,
            "rating": r.rating,
            "text": r.text,
            "date": r.created_at,
            "customer": "Anonymous" if r.anon else r.customer.user.person.first_name,
            })
            
        return Response(results)
    
    
class ApproveReviewView(APIView):
    permission_classes = [IsAdmin]
    
    def post(self,request, review_id):
        
        
        review = get_object_or_404(ReviewProduct, review_id=review_id)
        
        review.review_verified = True
        review.save()
        
        return Response({"message": "Review approved"})
    
    
class RejectReviewView(APIView):
    permission_classes = [IsAdmin]
    
    def post (self,request, review_id):
        
        
        review = get_object_or_404(
            ReviewProduct,
            review_id=review_id
        )
        
        review.delete()
        
        return Response({"message": "Review rejected"})