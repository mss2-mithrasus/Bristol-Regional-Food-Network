import csv
from django.http import HttpResponse
from django.db.models import Count, Sum
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import request, status
from rest_framework.permissions import IsAuthenticated
from product.models import Product, ProductCategory, Allergen,ProductAllergen
from product.serializers import ProductSerializer
from user_accounts.permissions import IsProducer
from user_accounts.models import ProducerAccount
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser

from .serializers import DashboardOrderSerializer, ProductCreateSerializer, ProducerOrderSerializer
from order_management.models import OrderStatusHistory, OrderStatusHistory, SubOrder
from payments.models import Commission
from django.db.models.functions import TruncWeek
from django.utils import timezone
from datetime import date, timedelta, datetime


class ProducerDashboardAPI(APIView):
    permission_classes = [IsAuthenticated, IsProducer]

    def get(self, request):
        producer = (ProducerAccount.objects.select_related("contact_person").filter(user=request.user).first())

        if not producer:
            return Response({"error": "Producer account not found"}, status=status.HTTP_404_NOT_FOUND)

        producer_name = producer.business_name
        products = Product.objects.filter(producer=producer)
        total_products = products.count()
        low_stock = products.filter(stock_quantity__lt=5).count()
        available_products = products.filter(availability_status=True).count()
        out_of_stock_products = products.filter(stock_quantity=0).count()
        low_stock_products = products.filter(stock_quantity__lt=5, stock_quantity__gt=0).count()
    
        active_orders = SubOrder.objects.filter(producer=producer).exclude(status="Delivered").count()

        delivered_orders = SubOrder.objects.filter(producer=producer, status="Delivered")

        revenue = sum(float(o.payout_amount or 0) * 0.95 for o in delivered_orders)
        
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
                "revenue": round(revenue, 2),
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
    permission_classes = [IsAuthenticated, IsProducer]

    def post(self, request):
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

        # Update fields
        product.name = request.data.get("name", product.name)
        product.description = request.data.get("description", product.description)
        product.price = request.data.get("price", product.price)
        product.unit = request.data.get("unit", product.unit)
        product.stock_quantity = request.data.get("stock_quantity", product.stock_quantity)
        availability = request.data.get("availability_status")
        if availability is not None:
            product.availability_status = str(availability).lower() in ["true", "1", "yes"]

        product.save()

        return Response({"message": "Product updated successfully"}, status=status.HTTP_200_OK)

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

        suborders = SubOrder.objects.filter(
            order__order_id=order_id,
            producer=producer
        )

        if not suborders.exists():
            return Response({"error": "Order not found"}, status=404)

        new_status = request.data.get("status")

        allowed = ["Pending", "Confirmed", "Ready", "Delivered"]

        if new_status not in allowed:
            return Response({"error": "Invalid status"}, status=400)
        for sub in suborders:
            old_status = sub.status

            if old_status != new_status:
                OrderStatusHistory.objects.create(
                    suborder=sub,
                    old_status=old_status,
                    new_status=new_status,
                    stock_time_change=producer
                )
        
        suborders.update(status=new_status)

        return Response({"message": "Status updated"})
    
class ProducerWeeklyPaymentsAPI(APIView):
    permission_classes = [IsAuthenticated, IsProducer]

    def get(self, request):

        producer = ProducerAccount.objects.filter(user=request.user).first()

        if not producer:
            return Response({"error": "Producer account not found"}, status=404)
        
        week_param = request.GET.get('week')
        # Get all delivered suborders
        suborders_query = SubOrder.objects.filter(
            producer=producer, 
            status="Delivered"
        ).select_related(
            "order", "order__customer"
        ).prefetch_related(
            "items__product"
        )
        # If week parameter provided, filter by that week
        if week_param:
            try:
                # Parse the week ending date
                week_end = datetime.strptime(week_param, '%Y-%m-%d').date()
                week_start = week_end - timedelta(days=6)
                
                suborders_query = suborders_query.filter(
                    order__created_at__date__range=[week_start, week_end]
                )
            except (ValueError, TypeError):
                return Response({"error": "Invalid week format"}, status=400)

        orders = []
        total_value = 0
        total_commission = 0
        total_payout = 0

        for sub in suborders_query:
            order_value = float(sub.payout_amount) if sub.payout_amount else 0
            commission = round(order_value * 0.05, 2)
            payout = round(order_value * 0.95, 2)

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

            total_value += order_value
            total_commission += commission
            total_payout += payout

        # Calculate tax year totals (April to March)
        today = timezone.now().date()
        if today.month < 4:
            tax_year_start = date(today.year - 1, 4, 1)
            tax_year_end = date(today.year, 3, 31)
            tax_year_display = f"{today.year-1}/{today.year}"
        else:
            tax_year_start = date(today.year, 4, 1)
            tax_year_end = date(today.year + 1, 3, 31)
            tax_year_display = f"{today.year}/{today.year+1}"

        # Get YTD totals
        ytd_suborders = SubOrder.objects.filter(
            producer=producer,
            status="Delivered",
            order__created_at__date__range=[tax_year_start, tax_year_end]
        )
        
        total_paid_ytd = sum(float(s.payout_amount or 0) * 0.95 for s in ytd_suborders)
        total_commission_ytd = sum(float(s.payout_amount or 0) * 0.05 for s in ytd_suborders)

        # Get week end date (if no week specified, use current week)
        if week_param:
            week_end_display = datetime.strptime(week_param, '%Y-%m-%d').strftime('%d %b %Y')
        else:
            # Default to current week (last Sunday)
            today = timezone.now().date()
            days_until_sunday = (6 - today.weekday()) % 7
            week_end = today + timedelta(days=days_until_sunday)
            week_end_display = week_end.strftime('%d %b %Y')
            week_param = week_end.isoformat()

        return Response({
            "total_value": round(total_value, 2),
            "commission": round(total_commission, 2),
            "payout": round(total_payout, 2),
            "status": "Processed" if suborders_query.exists() else "Pending",
            "settlement_ref": f"SETT-{week_param.replace('-', '')}-{producer.id}",
            "week_end": week_end_display,
            "processed_at": timezone.now().strftime('%d %b %Y %H:%M'),
            "tax_year": tax_year_display,
            "total_paid_ytd": round(total_paid_ytd, 2),
            "total_commission_ytd": round(total_commission_ytd, 2),
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

        # Get all weeks with delivered orders, grouped by week
        weekly_data = SubOrder.objects.filter(
            producer=producer,status="Delivered").annotate(week_ending=TruncWeek('order__created_at')
        ).values('week_ending').annotate(
            total_value=Sum('payout_amount'),
            order_count=Count('suborder_id')
        ).order_by('-week_ending').distinct() [:12]  # Last 12 weeks

        history = []
        for week_data in weekly_data:
            week_end = week_data['week_ending']
            if week_end:
                total_value = float(week_data['total_value'] or 0)
                history.append({
                    'week_ending': week_end.isoformat(),
                    'week_ending_formatted': week_end.strftime('%d %b %Y'),
                    'settlement_ref': f"SETT-{week_end.strftime('%Y%m%d')}-{producer.id}",
                    'total_value': total_value,
                    'commission': round(total_value * 0.05, 2),
                    'payout': round(total_value * 0.95, 2),
                    'status': 'Processed',
                    'order_count': week_data['order_count']
                })

        return Response({'history': history})
    
class ProducerWeeklyPaymentsCSV(APIView):
    permission_classes = [IsAuthenticated, IsProducer]

    def get(self, request):

        producer = ProducerAccount.objects.filter(user=request.user).first()
        week_param = request.GET.get("week")

        if not week_param:
            return Response({"error": "Week required"}, status=400)

        week_end = datetime.strptime(week_param, "%Y-%m-%d").date()
        week_start = week_end - timedelta(days=6)

        suborders = SubOrder.objects.filter(
            producer=producer,
            status="Delivered",
            order__created_at__date__range=[week_start, week_end]
        ).prefetch_related("items__product").select_related("order", "order__customer")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="settlement_{week_param}.csv"'

        writer = csv.writer(response)
        settlement_ref = f"SETT-{week_end.strftime('%Y%m%d')}-{producer.id}"
        writer.writerow(["Settlement Reference", settlement_ref])
        writer.writerow(["Week Ending", week_end.strftime("%d %b %Y")])
        writer.writerow(["Generated At", datetime.now().strftime("%Y-%m-%d %H:%M")])
        writer.writerow([])
        writer.writerow([
            "Order ID",
            "Customer",
            "Items",
            "Order Value",
            "Commission (5%)",
            "Producer Payout (95%)"
        ])

        for sub in suborders:

            order_value = float(sub.payout_amount)
            commission = round(order_value * 0.05, 2)
            payout = round(order_value * 0.95, 2)

            items = ", ".join([
                f"{i.product.name} x{i.quantity}"
                for i in sub.items.all()
            ])

            writer.writerow([
                sub.order.order_id,
                sub.order.customer.user.email,
                items,
                order_value,
                commission,
                payout
            ])

        return response