from sqlite3 import IntegrityError
from django.db.models import ProtectedError

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
from rest_framework.generics import UpdateAPIView

from .serializers import ProductCreateSerializer


class ProducerDashboardAPI(APIView):
    permission_classes = [IsAuthenticated, IsProducer]

    def get(self, request):
        producer = (
            ProducerAccount.objects
            .select_related("contact_person")
            .filter(user=request.user)
            .first()
        )

        if not producer:
            return Response({"error": "Producer account not found"}, status=status.HTTP_404_NOT_FOUND)

        producer_name = producer.business_name
        products = Product.objects.filter(producer=producer)
        total_products = products.count()
        low_stock = products.filter(stock_quantity__lt=5).count()
        recent_products = products.order_by("-product_id")[:5]
        recent_orders = []
        available_products = products.filter(availability_status=True).count()
        out_of_stock_products = products.filter(stock_quantity=0).count()
        low_stock_products = products.filter(stock_quantity__lt=5, stock_quantity__gt=0).count()
        for p in recent_products:
            recent_orders.append({
                "id": p.product_id,
                "customer": p.name,
                "items": f"Stock: {p.stock_quantity}",
                "status": "Available" if p.availability_status else "Out of stock"
            })

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
                "active_orders": 0,
                "revenue": 0,
                "low_stock": low_stock,
                "recent_orders": recent_orders,
                
                "product_status": {
                    "available": available_products,
                    "out_of_stock": out_of_stock_products,
                    "low_stock": low_stock_products,
                }
            },
            status=status.HTTP_200_OK,
        )


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
    orders = []  # TODO: get orders for this producer from DB
    return render(request, "order_management.html", {"orders": orders})


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
            #list of allergens
            allergens_id = request.data.getlist("allergens")
            for allergen_id in allergens_id:
                description = request.data.get(f"allergendescription{allergen_id}", "")
                if description or description == "":
                    ProductAllergen.objects.create(
                        product=product,
                        allergen_id=allergen_id,
                        description=description

                    )
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
        product.availability_status = request.data.get("availability_status", product.availability_status)

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