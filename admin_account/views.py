import hashlib 
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.views import View
from user_accounts.permissions import IsAdmin

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

from order_management.models import Order, SubOrder
from payments.models import PaymentTransaction
from django.views.decorators.http import require_GET


# Check if user is admin
def is_admin(user):
    return user.is_authenticated and user.role == "admin"


# Admin home page 
@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin), name="dispatch")
class AdminHomePageView(View):
    def get(self, request):
        pending_customers = CustomerAccount.objects.filter(account_verified=False)
        pending_producers = ProducerAccount.objects.filter(account_verified=False)

        return render(request, "admin_home_page.html", {
            "pending_customers": pending_customers,
            "pending_producers": pending_producers,
        })


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

    orders_qs = (
        Order.objects
        .filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            order_id__in=paid_order_ids,
        )
        .select_related("customer")
        .prefetch_related("suborders__producer")
    )

    aggregates = orders_qs.aggregate(
        total_order_value=Sum("total_amount"),
        total_commission=Sum("commission_amount"),
        order_count=Count("order_id"),
    )

    total_order_value = aggregates["total_order_value"] or Decimal("0.00")
    total_commission = aggregates["total_commission"] or Decimal("0.00")

    suborders_qs = SubOrder.objects.filter(order__in=orders_qs)
    total_producer_payments = suborders_qs.aggregate(
        total_payout=Sum("payout_amount")
    )["total_payout"] or Decimal("0.00")

    orders_data = []

    for order in orders_qs:
        producer_rows = []
        for s in order.suborders.all():
            producer_rows.append({
                "producer": str(s.producer),
                "subtotal": str(s.subtotal),
                "payout": str(s.payout_amount),
            })

        order_payout = sum(
            (s.payout_amount for s in order.suborders.all()),
            Decimal("0.00")
        )

        orders_data.append({
            "id": order.order_id,
            "customer": str(order.customer),
            "created_at": order.created_at.isoformat(),
            "status": order.order_status,
            "total": str(order.total_amount),
            "commission": str(order.commission_amount),
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
        "Commission Amount",
        "Producer Payout (sum of suborders)",
    ])

    for order in orders_qs:
        payout = sum((s.payout_amount for s in order.suborders.all()), Decimal("0.00"))
        writer.writerow([
            order.order_id,
            str(order.customer),
            order.created_at.isoformat(),
            order.order_status,
            str(order.total_amount),
            str(order.commission_amount),
            str(payout),
        ])

    return response

@require_GET
def AnalyticsData(request):
    """
    Returns analytics data for charts:
    - Payout per producer
    - Commission per producer
    - Orders per producer
    - Revenue over time
    - Commission over time
    """

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
        .annotate(total=Sum("order__commission_amount"))
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
        .annotate(total=Sum("commission_amount"))
        .order_by("created_at__date")
    )

    # Producer list for dropdown
    producers = list(
        ProducerAccount.objects.values("id", "business_name")
    )

    return JsonResponse({
        "payout": list(payout),
        "commission": list(commission),
        "orders": list(orders),
        "revenue": list(revenue),
        "commission_time": list(commission_time),
        "producers": producers,
    })