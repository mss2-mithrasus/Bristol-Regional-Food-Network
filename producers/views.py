import csv
from decimal import ROUND_HALF_UP, Decimal
from itertools import product
from django.http import HttpResponse
from django.db.models import Count, Sum
from django.db import transaction
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import request, status
from rest_framework.permissions import IsAuthenticated
from producers.models import ProducerSettlementOrder, SettlementReport
from product.models import Product, ProductCategory, Allergen,ProductAllergen
from product.serializers import ProductSerializer
from user_accounts.permissions import IsProducer
from user_accounts.models import ProducerAccount
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser

from .serializers import DashboardOrderSerializer, ProductCreateSerializer, ProducerOrderSerializer, SettlementReportSerializer
from order_management.models import OrderStatusHistory, OrderStatusHistory, SubOrder
from payments.models import Commission
from django.db.models.functions import TruncWeek
from django.utils import timezone
from datetime import date, timedelta, datetime
from product.models import SeasonalAvailability

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

        revenue = sum((o.payout_amount or Decimal('0')) * Decimal('0.95') 
              for o in delivered_orders)

        revenue = revenue.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
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
            
            return Response(
                {"message": "Product added successfully!", "product_id": product.product_id},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class ProducerProductListAPI(APIView):
    permission_classes = [IsAuthenticated, IsProducer]

    def get(self, request):
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
            data.append({
                "product_id": p.product_id,
                "name": p.name,
                "category": p.category.category_name if p.category else None,
                "category_id": p.category_id,
                "price": str(p.price),
                "unit": p.unit,
                "stock_quantity": p.stock_quantity,
                "availability_status": p.availability_status,
                "harvest_date": p.harvest_date.isoformat() if p.harvest_date else None,
                "image": p.image.url if p.image else None,
                "season_start_date": season.season_start_date.isoformat() if season and season.season_start_date else None,
                "season_end_date": season.season_end_date.isoformat() if season and season.season_end_date else None,
                "is_year_round": season.is_year_round if season else False,
            })

        return Response(data, status=status.HTTP_200_OK)
    

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

    
class ProducerUpdateProductAPI(APIView):
    permission_classes = [IsAuthenticated, IsProducer]

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
        product.price = request.data.get("price", product.price)
        product.unit = request.data.get("unit", product.unit)

        new_stock = request.data.get("stock_quantity", product.stock_quantity)
        product.stock_quantity = new_stock

        availability = request.data.get("availability_status")
        if availability is not None:
            product.availability_status = str(availability).lower() in ["true", "1", "yes"]
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
            season.season_start_date = start or None
            season.season_end_date = end or None
        season.save()
        product.save()

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

        suborders = (
            SubOrder.objects
            .filter(producer=producer)
            .select_related("order", "order__customer")
            .prefetch_related("items__product")
            .order_by("-order__created_at")
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
        
        # CHECK 48-HOUR PREPARATION WINDOW
        if new_status == "Confirmed" and suborders.first().status == "Pending":
            order_created_at = suborders.first().order.created_at
            hours_passed = (timezone.now() - order_created_at).total_seconds() / 3600
            if hours_passed < 48:
                hours_remaining = round(48 - hours_passed, 1)
                return Response({
                    "error": f"Cannot confirm this order yet. The 48-hour preparation window has not passed. "
                             f"Please wait {hours_remaining} more hours before confirming. "
                }, status=400)

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
        
        # ===== SEND NOTIFICATIONS TO CUSTOMER =====
        from notifications.models import Notification
        
        customer = order.customer.user  # Get the customer user
        is_delivery = suborders.first().delivery_date is not None
        # Create notification based on status
        if new_status == "Confirmed":
            title = f"Order #{order_id} Confirmed by {producer.business_name}"
            message = f"Good news! {producer.business_name} has confirmed your order."
            if note:
                message += f" Note from producer: {note}"
                
        elif new_status == "Ready":
            title = f"Order #{order_id} Ready for {'Collection' if not suborders.first().delivery_date else 'Delivery'}"
            message = f"Great news! {producer.business_name} has marked your order as ready. "
            if suborders.first().delivery_date:
                message += f"Expected delivery on {suborders.first().delivery_date.strftime('%d %b %Y')}."
            else:
                message += "You can now collect your order."
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
    suborders = SubOrder.objects.filter(
        producer=producer,
        status="Delivered",
        order__created_at__date__range=[start, end]
    )

    total_paid = sum((s.payout_amount or Decimal("0.00")) * Decimal("0.95") for s in suborders)
    total_commission = sum((s.payout_amount or Decimal("0.00")) * Decimal("0.05") for s in suborders)

    return total_paid, total_commission


def build_orders_from_suborders(suborders):
    orders = []

    for sub in suborders:
        order_value = Decimal(sub.payout_amount or 0)

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
            order__order_id=o.order_id,
            producer=producer
        ).select_related(
            "order", "order__customer"
        ).prefetch_related(
            "items__product"
        ).first()

        if sub:
            customer_name = f"{sub.order.customer.person.first_name} {sub.order.customer.person.last_name}"

            items = ", ".join([
                f"{i.product.name} x{i.quantity}"
                for i in sub.items.all()
            ])

            delivered_date = sub.order.created_at.strftime("%d %b %Y")
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

                suborders = suborders.filter(
                    order__created_at__date__range=[week_start, week_end]
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
        weekly_orders = (
            SubOrder.objects
            .filter(producer=producer)
            .annotate(week_ending=TruncWeek('order__created_at'))
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
        writer.writerow([])
        writer.writerow([
            "Order ID",
            "Order Value",
            "Commission",
            "Producer Payout"
        ])

        for o in settlement.settlement_orders.all():
            writer.writerow([
                o.order_id,
                float(o.order_value),
                float(o.commission_amount),
                float(o.producer_payout)
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
        suborders = SubOrder.objects.filter(
            producer=producer,
            status="Delivered",
            order__created_at__date__range=[week_start, week_end]
        ).select_related("order")

        total_value = Decimal("0.00")
        total_commission = Decimal("0.00")
        total_payout = Decimal("0.00")

        order_list = []

        for sub in suborders:
            order_value = Decimal(sub.payout_amount or 0)

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