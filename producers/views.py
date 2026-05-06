import csv
from itertools import product
from django.http import HttpResponse
# from django.db.models import Count, Sum
from django.db.models import Count, Sum, F, Subquery, OuterRef
from django.db import transaction
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import request, status
from rest_framework.permissions import IsAuthenticated
from producers.models import ProducerSettlementOrder, SettlementReport, LowStockAlert, SurplusDiscount
from product.models import Product, ProductCategory, Allergen,ProductAllergen
from product.serializers import ProductSerializer
from user_accounts.permissions import IsProducer
from user_accounts.models import ProducerAccount
from producers.low_stock_service import check_low_stock
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.decorators import api_view, permission_classes
from .serializers import DashboardOrderSerializer, ProductCreateSerializer, ProducerOrderSerializer, SettlementReportSerializer, SurplusDiscountSerializer
from order_management.models import OrderStatusHistory, OrderStatusHistory, SubOrder
from payments.models import Commission
from django.db.models.functions import TruncWeek
from django.utils import timezone
from datetime import date, timedelta, datetime
from product.models import SeasonalAvailability
from .utils import (
    expire_surplus_deals,
    deactivate_surplus_if_sold_out,
    deactivate_expired_products,
    get_earliest_fulfilment_date,
    is_product_valid_for_fulfilment,
    deactivate_surplus_if_not_fulfillable,
)

from django.utils.dateparse import parse_date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
class ProducerDashboardAPI(APIView):
    permission_classes = [IsAuthenticated, IsProducer]

    def get(self, request):
        producer = (ProducerAccount.objects.select_related("contact_person").filter(user=request.user).first())

        if not producer:
            return Response({"error": "Producer account not found"}, status=status.HTTP_404_NOT_FOUND)

        producer_name = producer.business_name
        products = Product.objects.filter(producer=producer)
        total_products = products.count()
        low_stock = products.filter(stock_quantity__lt=10).count()
        available_products = products.filter(availability_status=True).count()
        out_of_stock_products = products.filter(stock_quantity=0).count()
        low_stock_products = products.filter(stock_quantity__lt=10, stock_quantity__gt=0).count()
    
        active_orders = SubOrder.objects.filter(producer=producer).exclude(status="Delivered").count()

        delivered_orders = SubOrder.objects.filter(producer=producer, status="Delivered")

        revenue = sum((o.subtotal or Decimal('0')) * Decimal('0.95') 
              for o in delivered_orders),
        Decimal('0.00').quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        recent_suborders = (SubOrder.objects.filter(producer=producer).select_related("order", "order__customer").prefetch_related("items__product").order_by("-order__created_at")[:5])
        serializer = DashboardOrderSerializer(recent_suborders, many=True)

        return Response(
            {
                "producer_name": producer_name,
                "business_name": producer.business_name,
                "contact_name": (
                    f"{producer.contact_person.first_name} {producer.contact_person.last_name}"
                    if producer.contact_person else None
                ),
                "email": request.user.email,
                "total_products": total_products,
                "active_orders": active_orders,
                "revenue": (revenue),
                "low_stock": low_stock,
                "recent_orders": serializer.data,

                "product_status": {
                    "available": available_products,
                    "out_of_stock": out_of_stock_products,
                    "low_stock": low_stock_products,
                }
            },
            status=status.HTTP_200_OK,
        )

def dashboard(request):
    return render(request, "dashboard.html")

# Normal page renders (templates)
def dashboard(request):
    return render(request, "dashboard.html")


def product_management(request):
    return render(request, "product_management.html")


def add_product(request):
    """
    API-style: this view only renders the template.
    The actual saving is done by ProducerCreateProductAPI via fetch().
    """
    categories = ProductCategory.objects.all()
    allergens = Allergen.objects.all()

    return render(
        request,
        "add_product.html",
        {
            "categories": categories,
            "allergens": allergens,
        },
    )
def order_management(request):
    orders = []
    return render(request, "order_management.html", {"orders": orders})

def payments(request):
    return render(request, "payments.html")


class ProducerCreateProductAPI(APIView):
    """
    POST /producers/api/products/create/
    Expects multipart/form-data (FormData), supports image upload.
    """
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated, IsProducer]

    def post(self, request):
        
        print("FILES RECIEIVED:",request.FILES)
        print("DATA RECIEVED", request.data)
        serializer = ProductCreateSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            product = serializer.save()
            check_and_notify_seasonal(product)
            return Response(
                {"message": "Product added successfully!", "product_id": product.product_id},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class ProducerProductListAPI(APIView):
    permission_classes = [IsAuthenticated, IsProducer]

    def get(self, request):
        deactivate_expired_products()
        expire_surplus_deals()
        producer_account = ProducerAccount.objects.filter(user=request.user).first()
        if not producer_account:
            return Response({"error": "Producer account not found"}, status=status.HTTP_404_NOT_FOUND)

        products = (
            Product.objects
            .select_related("category")
            .filter(producer=producer_account)
            .order_by("-product_id")
        )

        data = []
        for p in products:
            season = p.seasonal_availability.first()
            # active_surplus = SurplusDiscount.objects.filter(
            #     product=p,
            #     status="active",
            #     expiry_date__gt=timezone.now()
            # ).first()
            active_surplus = None
            if is_product_valid_for_fulfilment(p):
                active_surplus = SurplusDiscount.objects.filter(
                    product=p,
                    status="active",
                    expiry_date__gt=timezone.now()
                ).first()

            days_until_best_before = None
            if p.best_before_date:
                days_until_best_before = (p.best_before_date - timezone.now().date()).days
            data.append({
                "product_id": p.product_id,
                "name": p.name,
                "category": p.category.category_name if p.category else None,
                "category_id": p.category_id,
                "price": str(p.price),
                "unit": p.unit,
                "stock_quantity": p.stock_quantity,
                "availability_status": p.availability_status,
                "is_expired": p.is_expired,
                "harvest_date": p.harvest_date.isoformat() if p.harvest_date else None,
                "best_before_date": p.best_before_date.isoformat() if p.best_before_date else None,
                "image": p.image.url if p.image else None,
                "season_start_date": season.season_start_date.isoformat() if season and season.season_start_date else None,
                "season_end_date": season.season_end_date.isoformat() if season and season.season_end_date else None,
                "is_year_round": season.is_year_round if season else False,
                "low_stock_threshold": p.low_stock_threshold,
                "has_active_surplus": active_surplus is not None,
                "active_surplus_id": active_surplus.surplus_id if active_surplus else None,
                "surplus_discount_percentage": active_surplus.discount_percentage if active_surplus else None,
                "surplus_expiry_date": active_surplus.expiry_date.isoformat() if active_surplus else None,
                "days_until_best_before": days_until_best_before,
               
            })

        return Response(data, status=status.HTTP_200_OK)
    
# felna added - producer-level bulk discount settings
class ProducerBulkSettingsAPI(APIView):

    permission_classes = [IsAuthenticated, IsProducer]

    def get(self, request):
        producer = ProducerAccount.objects.filter(user=request.user).first()
        if not producer:
            return Response({"error": "Producer account not found"}, status=404)

        return Response({
            "bulk_threshold_quantity": producer.bulk_threshold_quantity,
            "bulk_discount_percentage": (
                str(producer.bulk_discount_percentage)
                if producer.bulk_discount_percentage is not None
                else None
            ),
        }, status=200)

    def put(self, request):
        producer = ProducerAccount.objects.filter(user=request.user).first()
        if not producer:
            return Response({"error": "Producer account not found"}, status=404)

        threshold_raw = request.data.get("bulk_threshold_quantity")
        pct_raw = request.data.get("bulk_discount_percentage")

        
        threshold_value = (
            None if threshold_raw in (None, "", "null") else threshold_raw
        )
        pct_value = (
            None if pct_raw in (None, "", "null") else pct_raw
        )

        # Both must be set together, or both empty
        if (threshold_value is None) != (pct_value is None):
            return Response(
                {"error": "Bulk threshold and bulk discount percentage must be set together, or both empty."},
                status=400,
            )

        # Both empty - clear them
        if threshold_value is None and pct_value is None:
            producer.bulk_threshold_quantity = None
            producer.bulk_discount_percentage = None
            producer.save(update_fields=["bulk_threshold_quantity", "bulk_discount_percentage"])
            return Response({"message": "Bulk discount settings disabled."}, status=200)

        # Both filled - validate
        try:
            tq = int(threshold_value)
            if tq < 5 or tq > 100:
                return Response(
                    {"error": "Bulk threshold must be between 5 and 100."},
                    status=400,
                )
        except (TypeError, ValueError):
            return Response(
                {"error": "Bulk threshold must be a valid number."},
                status=400,
            )

        try:
            pct = Decimal(str(pct_value))
            if pct < Decimal("5") or pct > Decimal("25"):
                return Response(
                    {"error": "Bulk discount must be between 5% and 25%."},
                    status=400,
                )
        except (InvalidOperation, ValueError):
            return Response(
                {"error": "Bulk discount must be a valid number."},
                status=400,
            )

        producer.bulk_threshold_quantity = tq
        producer.bulk_discount_percentage = pct
        producer.save(update_fields=["bulk_threshold_quantity", "bulk_discount_percentage"])

        return Response({
            "message": "Bulk discount settings saved.",
            "bulk_threshold_quantity": tq,
            "bulk_discount_percentage": str(pct),
        }, status=200)
# end felna addition

class ProducerDeleteProductAPI(APIView):
    permission_classes = [IsAuthenticated, IsProducer]

    def delete(self, request, product_id):
        producer_account = ProducerAccount.objects.filter(user=request.user).first()
        if not producer_account:
            return Response({"error": "Producer account not found"}, status=status.HTTP_404_NOT_FOUND)

        product = Product.objects.filter(
            product_id=product_id,
            producer=producer_account
        ).first()

        if not product:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            product.delete()
        except Exception as e:
            return Response(
                {"error": f"Delete failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({"message": "Product deleted successfully"}, status=status.HTTP_200_OK)

def check_and_notify_seasonal(product):
    try:
        from notifications.seasonal_notify import notify_single_product_seasonal

        season = product.seasonal_availability.first()
        print(f"DEBUG season: {season}")
        print(f"DEBUG is_year_round: {season.is_year_round if season else 'NO SEASON'}")
        print(f"DEBUG start_date: {season.season_start_date if season else 'NONE'}")
        if season and season.season_start_date:
            from django.utils import timezone
            today = timezone.now().date()
            days = (season.season_start_date - today).days
            print(f"DEBUG days_until_start: {days}")

        count = notify_single_product_seasonal(product)
        print(f"DEBUG notification count returned: {count}")
    except Exception as e:
        print(f"Error sending seasonal notification: {e}")

    
class ProducerUpdateProductAPI(APIView):
    permission_classes = [IsAuthenticated, IsProducer]
    parser_classes = (MultiPartParser, FormParser)
    def put(self, request, product_id):
        producer_account = ProducerAccount.objects.filter(user=request.user).first()
        if not producer_account:
            return Response({"error": "Producer account not found"}, status=status.HTTP_404_NOT_FOUND)

        product = Product.objects.filter(
            product_id=product_id,
            producer=producer_account
        ).first()

        if not product:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

        # Capture old stock before any changes
        old_stock = int(product.stock_quantity)

        # Update fields
        product.name = request.data.get("name", product.name)
        product.description = request.data.get("description", product.description)
        #product.price = request.data.get("price", product.price)
        price_value = request.data.get("price")
        if price_value not in [None, ""]:
            try:
                product.price = Decimal(str(price_value))
            except (InvalidOperation, ValueError):
                return Response(
                    {"error": "Price must be a valid number."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        product.unit = request.data.get("unit", product.unit)
        #product.best_before_date = request.data.get("best_before_date") or None
        best_before_value = request.data.get("best_before_date")
        if best_before_value:
            parsed_best_before = parse_date(best_before_value)
            if not parsed_best_before:
                return Response(
                    {"error": "Best before date is invalid."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            product.best_before_date = parsed_best_before
        else:
            product.best_before_date = None

        new_stock = request.data.get("stock_quantity", product.stock_quantity)
        try:
            new_stock = int(new_stock)
        except (TypeError, ValueError):
            new_stock = product.stock_quantity

        product.stock_quantity = new_stock

        today = timezone.now().date()
        #earliest_fulfilment_date = get_earliest_fulfilment_date()

        # Expiry logic
        if product.best_before_date and product.best_before_date < today:
            product.is_expired = True
        else:
            product.is_expired = False

        # Availability logic
        # if product.stock_quantity <= 0:
        #     product.availability_status = False
        # elif product.best_before_date and product.best_before_date < earliest_fulfilment_date:
        #     product.availability_status = False
        # else:
        #     product.availability_status = True
        manual_available = request.data.get("availability_status")

        if manual_available is not None:
            product.availability_status = manual_available == "true"

        # Update low stock threshold if provided
        new_threshold = request.data.get("low_stock_threshold")
        if new_threshold is not None:
            try:
                product.low_stock_threshold = int(new_threshold)
            except (TypeError, ValueError):
                pass
        
                
        image = request.FILES.get("image")
        if image:
            product.image = image
        start = request.data.get("season_start_date")
        end = request.data.get("season_end_date")
        is_year_round = request.data.get("is_year_round") == "true"

        season, created = SeasonalAvailability.objects.get_or_create(product=product)

        season.is_year_round = is_year_round
        if is_year_round:
            season.season_start_date = None
            season.season_end_date = None
        else:
            season.season_start_date = parse_date(start) if start else None
            season.season_end_date = parse_date(end) if end else None
        season.save()
        check_and_notify_seasonal(product)
        product.save()
        check_low_stock(product)
        deactivate_surplus_if_sold_out(product)
        deactivate_surplus_if_not_fulfillable(product)
        # If stock increased, notify customers waiting for this product
        if int(new_stock) > old_stock:
            from django.db import transaction
            from notifications.utils import notify_stock_available
            from product.models import Product as FreshProduct
            product_id_to_notify = product.product_id

            def send_notifications():
                try:
                    fresh_product = FreshProduct.objects.get(product_id=product_id_to_notify)
                    notified = notify_stock_available(fresh_product)
                    print(f"Notified {notified} customers about {fresh_product.name}")
                except Exception as e:
                    print(f"Notification error: {e}")

            transaction.on_commit(send_notifications)

        return Response({"message": "Product updated successfully","image": product.image.url if product.image else None}, status=status.HTTP_200_OK)
    
class ProductUpdateView(APIView):
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def put(self, request, pk):
        product = Product.objects.get(pk=pk)

        serializer = ProductSerializer(product, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)   
    
class ProducerOrdersAPI(APIView):
    permission_classes = [IsAuthenticated, IsProducer]

    def get(self, request):

        producer = ProducerAccount.objects.filter(user=request.user).first()

        if not producer:
            return Response({"error": "Producer account not found"}, status=404)
        delivered_at_sq = (
            OrderStatusHistory.objects
            .filter(suborder=OuterRef('pk'), new_status='Delivered')
            .order_by('-order_status_changed_at')
            .values('order_status_changed_at')[:1]
        )
        suborders = (
            SubOrder.objects
            .filter(producer=producer)
            .select_related("order", "order__customer")
            .prefetch_related("items__product")
            .annotate(delivered_at=Subquery(delivered_at_sq))
            .order_by(F("delivery_date").asc(nulls_last=True), "order__created_at")
        )

        serializer = ProducerOrderSerializer(suborders, many=True)

        return Response({"orders": serializer.data})

class ProducerUpdateOrderStatusAPI(APIView):
    permission_classes = [IsAuthenticated, IsProducer]

    def patch(self, request, order_id):
        producer = ProducerAccount.objects.filter(user=request.user).first()
        
        if not producer:
            return Response({"error": "Producer account not found"}, status=404)

        # Get all suborders for this producer and order
        suborders = SubOrder.objects.filter(
            order__order_id=order_id,
            producer=producer
        )

        if not suborders.exists():
            return Response({"error": "Order not found"}, status=404)

        new_status = request.data.get("status")
        note = request.data.get("note", "")  # Optional note from producer

        allowed = ["Pending", "Confirmed", "Ready", "Delivered"]
        
        if new_status not in allowed:
            return Response({"error": "Invalid status"}, status=400)
            
        # Define the valid status flow
        status_flow = ["Pending", "Confirmed", "Ready", "Delivered"]
        
        # Check each suborder for valid status progression
        for sub in suborders:
            current_status = sub.status
            
            # If status is the same, skip
            if current_status == new_status:
                continue
                
            # Find indices in the flow
            try:
                current_index = status_flow.index(current_status)
                new_index = status_flow.index(new_status)
            except ValueError:
                return Response({
                    "error": f"Invalid status transition"
                }, status=400)
            
            # Check if trying to skip a stage
            if new_index != current_index + 1:
                # Calculate what the next status should be
                next_status = status_flow[current_index + 1] if current_index + 1 < len(status_flow) else None
                
                return Response({
                    "error": f"Cannot change status from {current_status} to {new_status}. "
                            f"{'Next status should be: ' + next_status if next_status else 'Order is complete.'}"
                }, status=400)
                
            if current_status == "Ready" and new_status == "Delivered":
                delivery_date = sub.delivery_date
                today = timezone.now().date()
                
                # If delivery date exists and today is before delivery date, block
                if delivery_date and today < delivery_date:
                    return Response({
                        "error": f"Cannot mark as delivered before the delivery/collection date ({delivery_date.strftime('%d %b %Y')}). "
                                f"Please wait until the delivery/collection date."
                    }, status=400)
        # Update all suborders for this producer
        updated_suborders = []
        for sub in suborders:
            old_status = sub.status
            
            if old_status != new_status:
                # Create status history
                OrderStatusHistory.objects.create(
                    suborder=sub,
                    old_status=old_status,
                    new_status=new_status,
                    stock_time_change=producer
                )
                
                # Update suborder status
                sub.status = new_status
                sub.save()
                updated_suborders.append(sub)
        
        # Check if ALL suborders for this order are now at the same status
        order = suborders.first().order
        all_suborders = order.suborders.all()
        
        # If all suborders have the same status, update the main order
        statuses = set(sub.status for sub in all_suborders)
        if len(statuses) == 1:
            # All suborders have the same status
            order.order_status = list(statuses)[0]
            order.save()
            print(f"Updated main order #{order.order_id} status to {order.order_status}")
        
        # SEND NOTIFICATIONS TO CUSTOMER
        from notifications.models import Notification
        
        customer = order.customer.user  # Get the customer user
        #is_delivery = suborders.first().delivery_date is not None
        #06/05/2026
        is_delivery = suborders.first().fulfillment_method == 'delivery'
        #06/05/2026 end 
        # Create notification based on status
        if new_status == "Confirmed":
            title = f"Order #{order_id} Confirmed by {producer.business_name}"
            message = f"Good news! {producer.business_name} has confirmed your order."
            if note:
                message += f" Note from producer: {note}"
                
        elif new_status == "Ready":
            #title = f"Order #{order_id} Ready for {'Collection' if not suborders.first().delivery_date else 'Delivery'}"
            # 06/05/2026
            title = f"Order #{order_id} Ready for {'Delivery' if is_delivery else 'Collection'}"
            # 06/05/2026 end 
            message = f"Great news! {producer.business_name} has marked your order as ready. "
            # if suborders.first().delivery_date:
            #     message += f"Expected delivery on {suborders.first().delivery_date.strftime('%d %b %Y')}."
            # else:
            #     message += "You can now collect your order."
            # 06/05/2026
            if is_delivery:
                message += f"Expected delivery on {suborders.first().delivery_date.strftime('%d %b %Y')}."
            else:
                message += f"Ready for collection on {suborders.first().delivery_date.strftime('%d %b %Y')}."
            # 06/05/2026 end 
            if note:
                message += f" Note from producer: {note}"
                
        elif new_status == "Delivered":
            if is_delivery:
                title = f"Order #{order_id} Delivered by {producer.business_name}"
                message = f"Your order from {producer.business_name} has been delivered. We hope you enjoy your products!"
            else:
                title = f"Order #{order_id} Collected from {producer.business_name}"
                message = f"Your order from {producer.business_name} has been collected. Thank you for shopping with us!"
            if note:
                message += f" Note from producer: {note}"
        else:
            # For other statuses, still send a notification
            title = f"Order #{order_id} Status Update"
            message = f"Your order from {producer.business_name} is now {new_status}."
            if note:
                message += f" Note: {note}"
        
        # Create the notification
        notification = Notification.objects.create(
            recipient=customer,
            notification_type='order_update',
            title=title,
            message=message,
            is_read=False,
            is_seen=False
        )
        
        print(f"Notification sent to {customer.email} for order #{order_id}")
        
        # If this is the last producer to mark as Delivered, send a summary
        if new_status == "Delivered":
            # Check if all suborders are delivered
            all_delivered = all(sub.status == "Delivered" for sub in all_suborders)
            if all_delivered:
                # Order is complete
                print(f"Order #{order_id} is now fully delivered!")
                
                # Send final notification
                Notification.objects.create(
                    recipient=customer,
                    notification_type='order_update',
                    title=f"Order #{order_id} Complete!",
                    message=f"All items from your order have been delivered. Thank you for shopping with us!",
                    is_read=False,
                    is_seen=False
                )

        return Response({
            "message": "Status updated successfully",
            "new_status": new_status,
            "order_id": order_id,
            "producer": producer.business_name,
            "notification_sent": True
        })

def get_tax_year():
    today = timezone.now().date()

    if today.month < 4:
        start = date(today.year - 1, 4, 1)
        end = date(today.year, 3, 31)
        display = f"{today.year-1}/{today.year}"
    else:
        start = date(today.year, 4, 1)
        end = date(today.year + 1, 3, 31)
        display = f"{today.year}/{today.year+1}"

    return start, end, display

def get_ytd_totals(producer, start, end):
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
        .filter(actual_delivered_date__date__range=[start, end])
    )

    # total_paid = sum((s.subtotal or Decimal("0.00")) * Decimal("0.95") for s in suborders)
    # total_commission = sum((s.subtotal or Decimal("0.00")) * Decimal("0.05") for s in suborders)
    total_paid = sum(
        ((s.subtotal or Decimal("0.00")) * Decimal("0.95")).quantize(Decimal("0.01"))
        for s in suborders
    ) or Decimal("0.00")

    total_commission = sum(
        ((s.subtotal or Decimal("0.00")) * Decimal("0.05")).quantize(Decimal("0.01"))
        for s in suborders
    ) or Decimal("0.00")

    return total_paid, total_commission

def _get_customer_name(sub):
    try:
        customer = sub.order.customer
        if customer.person:
            return f"{customer.person.first_name} {customer.person.last_name}"
        if customer.account_type == "community":
            return customer.communitygroup.organisation_name
        if customer.account_type == "restaurant":
            return customer.restaurant.organisation_name
        return customer.user.email
    except Exception:
        return "Unknown Customer"


def build_orders_from_suborders(suborders):
    orders = []

    for sub in suborders:
        order_value = Decimal(sub.subtotal or 0)

        commission = (order_value * Decimal("0.05")).quantize(Decimal("0.01"))
        payout = (order_value * Decimal("0.95")).quantize(Decimal("0.01"))

        items = ", ".join([
            f"{i.product.name} x{i.quantity}"
            for i in sub.items.all()
        ])

        orders.append({
            "order_id": sub.order.order_id,
            "customer_name": f"{sub.order.customer.person.first_name} {sub.order.customer.person.last_name}",
            "delivered_date": sub.order.created_at.strftime("%d %b %Y"),
            "items": items,
            "order_value": order_value,
            "commission": commission,
            "payout": payout,
        })

    return orders

def build_orders_from_settlement(settlement, producer):
    orders = []

    for o in settlement.settlement_orders.all():

        sub = SubOrder.objects.filter(
            orderorder_id=o.order_id,
            producer=producer
        ).select_related(
            "order", "ordercustomer"
        ).prefetch_related(
            "items__product"
        ).first()

        if sub:
            customer_name = _get_customer_name(sub)

            items = ", ".join([
                f"{i.product.name} x{i.quantity}"
                for i in sub.items.all()
            ])

            history = OrderStatusHistory.objects.filter(
                suborder=sub, new_status='Delivered'
            ).order_by('-order_status_changed_at').first()
            delivered_date = (
                history.order_status_changed_at.strftime("%d %b %Y")
                if history
                else sub.order.created_at.strftime("%d %b %Y")
            )
        else:
            customer_name = "Unknown"
            items = ""
            delivered_date = ""

        orders.append({
            "order_id": o.order_id,
            "customer_name": customer_name,
            "delivered_date": delivered_date,
            "items": items,
            "order_value": o.order_value,
            "commission": o.commission_amount,
            "payout": o.producer_payout,
        })

    return orders

class ProducerWeeklyPaymentsAPI(APIView):
    permission_classes = [IsAuthenticated, IsProducer]

    def get(self, request):

        producer = ProducerAccount.objects.filter(user=request.user).first()

        if not producer:
            return Response({"error": "Producer account not found"}, status=404)
        
        week_param = request.GET.get('week')
        # Tax year + YTD
        tax_year_start, tax_year_end, tax_year_display = get_tax_year()
        total_paid_ytd, total_commission_ytd = get_ytd_totals(
            producer, tax_year_start, tax_year_end
        )

        if week_param:
            try:
                week_end = datetime.strptime(week_param, '%Y-%m-%d').date()
                week_start = week_end - timedelta(days=6)

                settlement = SettlementReport.objects.filter(
                    producer=producer,
                    week_start=week_start,
                    week_end=week_end
                ).prefetch_related("settlement_orders").first()

                if settlement:
                    orders = build_orders_from_settlement(settlement, producer)

                    return Response({
                        "total_value": settlement.total_order_value,
                        "commission": settlement.commission_amount,
                        "payout": settlement.payout_amount,
                        "status": settlement.payment_status,
                        "settlement_ref": f"SETT-{week_param.replace('-', '')}-{producer.id}",
                        "week_end": week_end.strftime('%d %b %Y'),
                        "tax_year": tax_year_display,
                        "total_paid_ytd": total_paid_ytd,
                        "total_commission_ytd": total_commission_ytd,
                        "orders": orders
                    })

            except Exception as e:
                print("DB LOAD ERROR:", e)

        if week_param:
            try:
                week_end = datetime.strptime(week_param, '%Y-%m-%d').date()
                week_start = week_end - timedelta(days=6)
                today = timezone.now().date()

                if week_end < today:
                    delivered_date_sq = (
                    OrderStatusHistory.objects
                    .filter(suborder=OuterRef('pk'), new_status='Delivered')
                    .order_by('-order_status_changed_at')
                    .values('order_status_changed_at')[:1]
                    )
                    suborders =( SubOrder.objects.filter(producer=producer, status="Delivered")
                        .annotate(actual_delivered_date=Subquery(delivered_date_sq))
                        .filter(actual_delivered_date__date__range=[week_start, week_end])
                        )

                    if suborders.exists():
                        # Auto-create the settlement
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
                                transaction_id=None,
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

                        # Return the newly created settlement
                        orders = build_orders_from_settlement(settlement, producer)
                        return Response({
                            "total_value": settlement.total_order_value,
                            "commission": settlement.commission_amount,
                            "payout": settlement.payout_amount,
                            "status": settlement.payment_status,
                            "settlement_ref": f"SETT-{week_param.replace('-', '')}-{producer.id}",
                            "week_end": week_end.strftime('%d %b %Y'),
                            "tax_year": tax_year_display,
                            "total_paid_ytd": total_paid_ytd,
                            "total_commission_ytd": total_commission_ytd,
                            "orders": orders
                        })
            except Exception as e:
                print("AUTO-SETTLEMENT ERROR:", e)

        # Fallback: return live data for current/incomplete weeks

        suborders = SubOrder.objects.filter(
            producer=producer,
            status="Delivered"
        ).select_related(
            "order", "order__customer"
        ).prefetch_related(
            "items__product"
        )

        if week_param:
            try:
                week_end = datetime.strptime(week_param, '%Y-%m-%d').date()
                week_start = week_end - timedelta(days=6)

                delivered_date_sq = (
                    OrderStatusHistory.objects
                    .filter(suborder=OuterRef('pk'), new_status='Delivered')
                    .order_by('-order_status_changed_at')
                    .values('order_status_changed_at')[:1]
                )
                suborders = suborders.annotate(
                    actual_delivered_date=Subquery(delivered_date_sq)
                ).filter(
                    actual_delivered_date__date__range=[week_start, week_end]
                )
            except:
                return Response({"error": "Invalid week format"}, status=400)

        orders = build_orders_from_suborders(suborders)

        total_value = sum(o["order_value"] for o in orders)
        total_commission = sum(o["commission"] for o in orders)
        total_payout = sum(o["payout"] for o in orders)

        if week_param:
            week_end_display = datetime.strptime(week_param, '%Y-%m-%d').strftime('%d %b %Y')
        else:
            today = timezone.now().date()
            days_until_sunday = (6 - today.weekday()) % 7
            week_end = today + timedelta(days=days_until_sunday)
            week_end_display = week_end.strftime('%d %b %Y')
            week_param = week_end.isoformat()

        return Response({
            "total_value": total_value,
            "commission": total_commission,
            "payout": total_payout,
            "status": "Processed" if suborders.exists() else "Pending",
            "settlement_ref": f"SETT-{week_param.replace('-', '')}-{producer.id}",
            "week_end": week_end_display,
            "tax_year": tax_year_display,
            "total_paid_ytd": total_paid_ytd,
            "total_commission_ytd": total_commission_ytd,
            "orders": orders
        }) 
class ProducerWeeklyPaymentsWeeksAPI(APIView):
    """Return list of available settlement weeks"""
    permission_classes = [IsAuthenticated, IsProducer]

    def get(self, request):
        producer = ProducerAccount.objects.filter(user=request.user).first()

        if not producer:
            return Response({"error": "Producer account not found"}, status=404)

        # Get all delivered orders and group by week
        delivered_date_sq = (
        OrderStatusHistory.objects
        .filter(suborder=OuterRef('pk'), new_status='Delivered')
        .order_by('-order_status_changed_at')
        .values('order_status_changed_at')[:1]
        )
        weekly_orders = (
            SubOrder.objects
            .filter(producer=producer, status="Delivered")
            .annotate(actual_delivered_date=Subquery(delivered_date_sq))
            .annotate(week_ending=TruncWeek('actual_delivered_date'))
            .values('week_ending')
            .annotate(
                order_count=Count('suborder_id'),
                total_value=Sum('payout_amount')
            )
            .order_by('-week_ending')
        )
        

        weeks = []
        for week_data in weekly_orders:
            week_end = week_data['week_ending']
            if week_end:
                # Check if this week would be "Processed" (has orders)
                weeks.append({
                    'week_ending': week_end.isoformat(),
                    'end_date_formatted': week_end.strftime('%d %b %Y'),
                    'status': 'Processed',
                    'order_count': week_data['order_count'],
                    'total_value': float(week_data['total_value'] or 0)
                })

        return Response({'weeks': weeks})

class ProducerWeeklyPaymentsHistoryAPI(APIView):
    """Return historical settlements"""
    permission_classes = [IsAuthenticated, IsProducer]

    def get(self, request):
        producer = ProducerAccount.objects.filter(user=request.user).first()

        if not producer:
            return Response({"error": "Producer account not found"}, status=404)

        settlements = SettlementReport.objects.filter(
            producer=producer
        ).order_by("-week_end")[:12]  # last 12 weeks

        history = []

        for s in settlements:
            history.append({
                "week_ending": s.week_end.isoformat(),
                "week_ending_formatted": s.week_end.strftime('%d %b %Y'),
                "settlement_ref": f"SETT-{s.week_end.strftime('%Y%m%d')}-{producer.id}",
                "total_value": s.total_order_value,
                "commission": s.commission_amount,
                "payout": s.payout_amount,
                "status": s.payment_status,
            })

        return Response({"history": history})
    
class ProducerWeeklyPaymentsCSV(APIView):
    permission_classes = [IsAuthenticated, IsProducer]

    def get(self, request):

        producer = ProducerAccount.objects.filter(user=request.user).first()
        week_param = request.GET.get("week")

        if not week_param:
            return Response({"error": "Week required"}, status=400)

        week_end = datetime.strptime(week_param, "%Y-%m-%d").date()
        week_start = week_end - timedelta(days=6)

        settlement = SettlementReport.objects.filter(
            producer=producer,
            week_start=week_start,
            week_end=week_end
        ).prefetch_related("settlement_orders").first()

        if not settlement:
            return Response({"error": "Settlement not found"}, status=404)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="settlement_{week_param}.csv"'

        writer = csv.writer(response)

        writer.writerow(["Settlement Reference", f"SETT-{week_end.strftime('%Y%m%d')}-{producer.id}"])
        writer.writerow(["Week Ending", week_end.strftime("%d %b %Y")])
        writer.writerow(["Status", settlement.payment_status])
        writer.writerow(["Total Order Value", f"{settlement.total_order_value:.2f}"])
        writer.writerow(["Commission (5%)", f"{settlement.commission_amount:.2f}"])
        writer.writerow(["Producer Payout (95%)", f"{settlement.payout_amount:.2f}"])
        writer.writerow([])
        writer.writerow([
            "Order ID",
            "customer",
            "Delivered Date",
            "Items",
            "Order Value",
            "Commission (5%)",
            "Producer Payout (95%)"
        ])

        for o in settlement.settlement_orders.all():
            sub = SubOrder.objects.filter(
                orderorder_id=o.order_id, producer=producer
            ).select_related("order", "ordercustomer").prefetch_related("items__product").first()

            customer_name = _get_customer_name(sub) if sub else "Unknown"
            items = ", ".join(f"{i.product.name} x{i.quantity}" for i in sub.items.all()) if sub else ""

            history = OrderStatusHistory.objects.filter(
                suborder=sub, new_status='Delivered'
            ).order_by('-order_status_changed_at').first() if sub else None
            delivered_date = history.order_status_changed_at.strftime("%d %b %Y") if history else ""

            writer.writerow([
                o.order_id,
                customer_name,
                delivered_date,
                items,
                f"{o.order_value:.2f}",
                f"{o.commission_amount:.2f}",
                f"{o.producer_payout:.2f}"
            ])

        return response
    
class ProcessSettlementAPI(APIView):
    permission_classes = [IsAuthenticated, IsProducer]

    def post(self, request):

        producer = ProducerAccount.objects.filter(user=request.user).first()

        if not producer:
            return Response({"error": "Producer not found"}, status=404)

        week_param = request.data.get("week")

        if not week_param:
            return Response({"error": "Week is required"}, status=400)

        try:
            week_end = datetime.strptime(week_param, "%Y-%m-%d").date()
            week_start = week_end - timedelta(days=6)
        except:
            return Response({"error": "Invalid date"}, status=400)

        #  Prevent duplicates
        existing = SettlementReport.objects.filter(
            producer=producer,
            week_start=week_start,
            week_end=week_end
        ).first()

        if existing:
            serializer = SettlementReportSerializer(existing)
            return Response({
                "created": False,
                "data": serializer.data
            }, status=200)

        #  Fetch suborders
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
            .filter(actual_delivered_datedaterange=[week_start, week_end])
            .select_related("order")
        )

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

        # Save everything safely
        with transaction.atomic():

            settlement = SettlementReport.objects.create(
                producer=producer,
                transaction_id=None,
                week_start=week_start,
                week_end=week_end,
                total_order_value=total_value,
                commission_amount=total_commission,
                payout_amount=total_payout,
                payment_status="Processed",
            )

            bulk_orders = [
                ProducerSettlementOrder(
                    settlement_report=settlement,
                    order_id=o["order_id"],
                    order_value=o["order_value"],
                    commission_amount=o["commission"],
                    producer_payout=o["payout"],
                )
                for o in order_list
            ]

            ProducerSettlementOrder.objects.bulk_create(bulk_orders)

        serializer = SettlementReportSerializer(settlement)

        return Response({
            "created": True,
            "data": serializer.data
        }, status=201)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsProducer])
def get_low_stock_alerts(request):
    """Get all active low stock alerts for the producer"""
    producer = ProducerAccount.objects.filter(user=request.user).first()
    
    if not producer:
        return Response({'error': 'Producer not found'}, status=404)
    
    alerts = LowStockAlert.objects.filter(
        producer=producer,
        is_resolved=False,
        is_active=True
    ).select_related('product')
    
    alert_data = []
    for alert in alerts:
        local_created_at = timezone.localtime(alert.created_at)
        alert_data.append({
            'alert_id': alert.alert_id,
            'product_id': alert.product.product_id,
            'product_name': alert.product.name,
            'product_image': alert.product.image.url if alert.product.image else None,
            'current_stock': alert.current_stock,
            'threshold': alert.threshold,
            'unit': alert.product.unit,
            'created_at': alert.created_at.isoformat(),
            'created_at_formatted': local_created_at.strftime('%d %b %Y %H:%M'),
            'status': 'active'
        })
    
    return Response({
        'alerts': alert_data,
        'alert_count': len(alert_data)
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsProducer])
def resolve_low_stock_alert(request, alert_id):
    """Manually resolve a low stock alert"""
    producer = ProducerAccount.objects.filter(user=request.user).first()
    
    if not producer:
        return Response({'error': 'Producer not found'}, status=404)
    
    try:
        alert = LowStockAlert.objects.get(
            alert_id=alert_id,
            producer=producer,
            is_resolved=False
        )
    except LowStockAlert.DoesNotExist:
        return Response({'error': 'Alert not found'}, status=404)
    
    alert.is_resolved = True
    alert.is_active = False
    alert.resolved_at = timezone.now()
    alert.save()
    
    return Response({
        'success': True,
        'message': f'Alert for {alert.product.name} resolved'
    })
# Micaiah added - 13-04-2026
# Surplus discount 
class ProducerCreateSurplusDealAPI(APIView):
    permission_classes = [IsAuthenticated, IsProducer]

    def post(self, request, product_id):
        deactivate_expired_products()
        expire_surplus_deals()

        producer_account = ProducerAccount.objects.filter(user=request.user).first()
        if not producer_account:
            return Response({"error": "Producer account not found"}, status=404)

        product = Product.objects.filter(
            product_id=product_id,
            producer=producer_account
        ).first()

        if not product:
            return Response({"error": "Product not found"}, status=404)
        
        if not is_product_valid_for_fulfilment(product):
            return Response(
                {
                    "error": "This product cannot be offered as a surplus deal because its best before date is earlier than the earliest customer fulfilment date."
                },
                status=400
            )
            
        existing_active = SurplusDiscount.objects.filter(
            product=product,
            status="active",
            expiry_date__gt=timezone.now()
        ).first()

        if existing_active:
            return Response(
                {"error": "This product already has an active surplus deal."},
                status=400
            )

        payload = request.data.copy()
        payload["product"] = product.product_id

        serializer = SurplusDiscountSerializer(data=payload)
        if serializer.is_valid():
            deal = serializer.save(status="active")
            
            # Send notifications to customers (mithra added)
            from notifications.utils import notify_customers_surplus_deal
            notify_customers_surplus_deal(product, deal.discount_percentage)
            
            return Response(SurplusDiscountSerializer(deal).data, status=201)

        return Response(serializer.errors, status=400)


class ProducerSurplusDealsAPI(APIView):
    permission_classes = [IsAuthenticated, IsProducer]

    def get(self, request):
        expire_surplus_deals()

        producer_account = ProducerAccount.objects.filter(user=request.user).first()
        if not producer_account:
            return Response({"error": "Producer account not found"}, status=404)

        all_deals = (
            SurplusDiscount.objects
            .filter(product__producer=producer_account)
            .select_related("product")
            .order_by("-date_discount_created")
        )

        deals = [deal for deal in all_deals if is_product_valid_for_fulfilment(deal.product) or deal.status != "active"]

        serializer = SurplusDiscountSerializer(deals, many=True)
        return Response(serializer.data, status=200)


class ProducerRemoveSurplusDealAPI(APIView):
    permission_classes = [IsAuthenticated, IsProducer]

    def post(self, request, surplus_id):
        producer_account = ProducerAccount.objects.filter(user=request.user).first()
        if not producer_account:
            return Response({"error": "Producer account not found"}, status=404)

        deal = SurplusDiscount.objects.filter(
            surplus_id=surplus_id,
            product__producer=producer_account
        ).first()

        if not deal:
            return Response({"error": "Surplus deal not found"}, status=404)

        deal.status = "cancelled"
        deal.save(update_fields=["status", "updated_at"])

        return Response({"message": "Surplus deal removed successfully."}, status=200)