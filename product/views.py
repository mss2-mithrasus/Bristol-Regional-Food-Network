from django.shortcuts import render, get_object_or_404, redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Product, ProductCategory, ProductAllergen, ReviewProduct
from .serializers import ProductSerializer, ProductCategorySerializer, ProductAllergenSerializer
from rest_framework.permissions import AllowAny
from rest_framework import generics
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view
from rest_framework.decorators import api_view, permission_classes
from user_accounts.permissions import IsProducer
from user_accounts.permissions import IsCustomer
from django.contrib.auth.decorators import login_required
from shopping_cart.utils import get_available_stock 
from product.utils import food_miles
from producers.models import SurplusDiscount
from producers.utils import (
    expire_surplus_deals,
    deactivate_expired_products,
    is_product_valid_for_fulfilment,
)
from django.utils import timezone
from django.db.models import Avg

def add_customer_availability_fields(product_dict, product, available_stock):
    product_dict["available_stock"] = available_stock
    product_dict["stock_quantity"] = product.stock_quantity

    if available_stock <= 0:
        product_dict["can_buy"] = False
        product_dict["unavailable_reason"] = "Out of stock"
    elif not is_product_valid_for_fulfilment(product):
        product_dict["can_buy"] = False
        product_dict["unavailable_reason"] = "Unavailable as fulfilment date after best before."
    else:
        product_dict["can_buy"] = True
        product_dict["unavailable_reason"] = ""

    return product_dict

# api to return all product categories for the frontend page

class CustomerAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    
    def get(self, request):
        # getting all the categories stored in the database
        categories = ProductCategory.objects.all()
        # convert category object to json
        category_serializer = ProductCategorySerializer(categories, many=True)
        # debug to check categories
        print("categories in db:", [c.category_name for c in categories])
        
        # return category data to front end
        return Response({"categories": category_serializer.data}, status=status.HTTP_200_OK )
    
def orders(request):
    return render(request, "orders.html")

def about_us(request):
    return render(request, "about_us.html")

# api to return products in a category
class CategoryProductsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    
    def get(self, request, category_name):
        deactivate_expired_products()
        expire_surplus_deals()
        # get category object
        category = ProductCategory.objects.filter(category_name__iexact=category_name).first()
        if not category:
            return Response({"error": "Category not found"}, status=status.HTTP_404_NOT_FOUND)
        # getting all the available products in the category
        #products = Product.objects.filter(category=category, availability_status=True)
        products = Product.objects.filter(
            category=category,
            availability_status=True,
            # stock_quantity__gt=0,
            is_expired=False
        )
        # Convert products to JSON with available stock calculation
        product_data = []
        for product in products:
            # if not is_product_valid_for_fulfilment(product):
            #     continue
            # Calculate available stock for this user
            available_stock = get_available_stock(
                product, 
                exclude_user=request.user if request.user.is_authenticated else None
            )
            
            serializer = ProductSerializer(product)
            product_dict = serializer.data

            # Surplus deal
            # active_deal = SurplusDiscount.objects.filter(
            #     product=product,
            #     status="active",
            #     expiry_date__gt=timezone.now()
            # ).first()

            # if active_deal:
            #     original_price = float(product.price)
            #     discounted_price = round(original_price * (100 - active_deal.discount_percentage) / 100, 2)

            #     product_dict["has_surplus_discount"] = True
            #     product_dict["original_price"] = original_price
            #     product_dict["discounted_price"] = discounted_price
            #     product_dict["discount_percentage"] = active_deal.discount_percentage
            #     product_dict["surplus_note"] = active_deal.note
            #     product_dict["surplus_expiry_date"] = active_deal.expiry_date.isoformat()
            # else:
            #     product_dict["has_surplus_discount"] = False
            #     product_dict["original_price"] = float(product.price)
            #     product_dict["discounted_price"] = float(product.price)
            #     product_dict["discount_percentage"] = None
            #     product_dict["surplus_note"] = ""
            #     product_dict["surplus_expiry_date"] = None
            # Add available_stock to the product data
            product_dict = add_customer_availability_fields(
                product_dict,
                product,
                available_stock
            )
            product_data.append(product_dict)
        
        # return category name and products
        return Response({
            "category": category.category_name,
            "products": product_data
        }, status=status.HTTP_200_OK)


def category_page(request, category_name):
    return render(request, 'categories.html', {'category_name': category_name})

def product_detail(request, product_id):
    product = get_object_or_404(Product, product_id=product_id)
    return render(request, 'product_detail.html', {'product_id': product_id})
def surplus_deals_page(request):
    return render(request, 'surplus_deals.html')

class ProductSearchAPIView(APIView):
    def get(self, request):
        deactivate_expired_products()
        expire_surplus_deals()
        # get search query from url
        query = request.GET.get("q", "")
        # get filter
        filter_value = request.GET.get("filter", "")
        #products = Product.objects.filter(availability_status=True)
        products = Product.objects.filter(
            availability_status=True,
            #stock_quantity__gt=0,
            is_expired=False
        )
        # get category
        category = request.GET.get("category")
        
        # filter by category
        if category:
            products = products.filter(category__category_name=category)
        
        # if there is a query then filter products by the product name, producer name, or allergen name
        if query:
            # split query to words
            words = query.split()
            
            # search conditions
            filtering =(
                Q(name__icontains=query) | Q(allergens__name__icontains=query) | Q(producer__business_name__icontains=query)
            )
            # if user searches organic display all organic products
            if "organic" in query.lower():
                filtering |= Q(organic_certified=True)
                
            # if a query has multiple words search description
            if len(words) >= 2:
                filter_by_description = Q()
                for word in words:
                    filter_by_description |= Q(description__icontains=word)
                    
                filtering |= filter_by_description
            # apply filters
            products = products.filter(filtering).distinct()
            
        # organic filter from dropdown
        if filter_value.lower() == "organic":
            products = products.filter(organic_certified=True)
        
        # Convert products to JSON with available stock calculation
        product_data = []
        for product in products:
            # if not is_product_valid_for_fulfilment(product):
            #     continue
            # Calculate available stock for this user
            # If user is authenticated, exclude their own reservations
            # If user is not authenticated, show all available stock
            available_stock = get_available_stock(
                product, 
                exclude_user=request.user if request.user.is_authenticated else None
            )
            
            # Get the serialized product data first
            serializer = ProductSerializer(product)
            product_dict = serializer.data

            
            # Add available_stock to the product data
            product_dict = add_customer_availability_fields(
                product_dict,
                product,
                available_stock
            )
            product_data.append(product_dict)
        
        # return products
        return Response({
            "products": product_data
        }, status=status.HTTP_200_OK)


class ProductDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request, product_id):
        request.session[f"viewed_{product_id}"] = True
        deactivate_expired_products()
        expire_surplus_deals()
        # getting product based on primary key
        product = get_object_or_404(Product, product_id=product_id)
        # if not is_product_valid_for_fulfilment(product):
        #     return Response(
        #         {"error": "This product is no longer available for fulfilment."},
        #         status=status.HTTP_404_NOT_FOUND
        #     )
        if not product.availability_status or product.is_expired:
            return Response(
                {"error": "This product is not available."},
                status=status.HTTP_404_NOT_FOUND
            )
        # Calculate available stock for this product
        available_stock = get_available_stock(
            product, 
            exclude_user=request.user if request.user.is_authenticated else None
        )

        serializer = ProductSerializer(product)
        product_dict = serializer.data
    
        
        product_dict = add_customer_availability_fields(
            product_dict,
            product,
            available_stock
        )
        average_rating = ReviewProduct.objects.filter(product=product, review_verified=True).aggregate(
            avg=Avg('rating')
        )['avg']
        
        product_dict['average_rating'] = round(average_rating, 1) if average_rating else None
        # Surplus deal
        # active_deal = SurplusDiscount.objects.filter(
        #     product=product,
        #     status="active",
        #     expiry_date__gt=timezone.now()
        # ).first()

        # if active_deal:
        #     original_price = float(product.price)
        #     discounted_price = round(original_price * (100 - active_deal.discount_percentage) / 100, 2)

        #     product_dict["has_surplus_discount"] = True
        #     product_dict["original_price"] = original_price
        #     product_dict["discounted_price"] = discounted_price
        #     product_dict["discount_percentage"] = active_deal.discount_percentage
        #     product_dict["surplus_note"] = active_deal.note
        #     product_dict["surplus_expiry_date"] = active_deal.expiry_date.isoformat()
        # else:
        #     product_dict["has_surplus_discount"] = False
        #     product_dict["original_price"] = float(product.price)
        #     product_dict["discounted_price"] = float(product.price)
        #     product_dict["discount_percentage"] = None
        #     product_dict["surplus_note"] = ""
        #     product_dict["surplus_expiry_date"] = None

# getting all the allergens for the product
        allergens = product.productallergen_set.all()
        allergens_serializer = ProductAllergenSerializer(allergens, many=True)

        #food miles

        customer = request.user.customeraccount

        customer_postcode = customer.address.postcode
        producer_postcode = product.producer.address.postcode

        print("customer postcode:", customer_postcode)
        print("producer postcode:", producer_postcode)

        farm_miles = food_miles(customer_postcode, producer_postcode)
        
        
        
        
        reviews = ReviewProduct.objects.filter(
            product=product,
            review_verified=True
            
            
        ).select_related("customer")
        
        reviews_data = [
            {
            "review_id": r.review_id,
            "rating": r.rating,
            "text": r.text,
            "date": r.created_at,
            "customer": "Anonymous" if r.anon else r.customer.user.person.first_name
        }
            for r in reviews
            
            ]
        # felna - account type for bulk discount eligibility
        try:
            account_type = request.user.customeraccount.account_type
        except Exception:
            account_type = "normal"
        
        producer = product.producer
        producer_bulk_threshold = producer.bulk_threshold_quantity
        producer_bulk_pct = (
            str(producer.bulk_discount_percentage)
            if producer.bulk_discount_percentage is not None
            else None
        )
        # end felna change

        #return Response({"product": serializer.data, "farm_miles": farm_miles, "allergens": allergens_serializer.data}, status=status.HTTP_200_OK)
        return Response(
            {
                "product": product_dict,
                "farm_miles": farm_miles,
                "allergens": allergens_serializer.data,
                "reviews": reviews_data,
                # felna - bulk discount info for product page hint
                "account_type": account_type,
                "is_bulk_eligible": account_type in ["community", "restaurant"],
                "producer_bulk_threshold_quantity": producer_bulk_threshold,
                "producer_bulk_discount_percentage": producer_bulk_pct,
                #ended
            },
            status=status.HTTP_200_OK
        )
# Micaiah added - 13-04-2026 - Surplus discount
class SurplusDealsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        deactivate_expired_products()
        expire_surplus_deals()

        deals = (
            SurplusDiscount.objects
            .filter(
                status="active",
                expiry_date__gt=timezone.now(),
                product__availability_status=True,
                product__stock_quantity__gt=0
            )
            .select_related("product", "product__producer", "product__category")
            .order_by("-date_discount_created")
        )

        product_data = []
        for deal in deals:
            product = deal.product
            if not is_product_valid_for_fulfilment(product):
                continue
            available_stock = get_available_stock(
                product,
                exclude_user=request.user if request.user.is_authenticated else None
            )

            # serializer = ProductSerializer(product)
            # product_dict = serializer.data
            # product_dict["producer_name"] = product.producer.business_name

            # original_price = float(product.price)
            # discounted_price = round(
            #     original_price * (100 - deal.discount_percentage) / 100,
            #     2
            # )
            # product_dict["producer_name"] = product.producer.business_name
            # product_dict["available_stock"] = available_stock
            # product_dict["stock_quantity"] = product.stock_quantity
            # product_dict["surplus_id"] = deal.surplus_id
            # product_dict["has_surplus_discount"] = True
            # product_dict["original_price"] = original_price
            # product_dict["discounted_price"] = discounted_price
            # product_dict["discount_percentage"] = deal.discount_percentage
            # product_dict["surplus_note"] = deal.note
            # product_dict["surplus_expiry_date"] = deal.expiry_date.isoformat()
            serializer = ProductSerializer(product)
            product_dict = serializer.data
            product_dict["producer_name"] = product.producer.business_name
            product_dict["available_stock"] = available_stock
            product_dict["stock_quantity"] = product.stock_quantity
            product_dict["surplus_id"] = deal.surplus_id
            product_data.append(product_dict)

        return Response({"products": product_data}, status=status.HTTP_200_OK)
    
class ProductCategoryCreateAPIView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        # json data is converted to a serializer
        serializer = ProductCategorySerializer(data=request.data)
        if serializer.is_valid():
            # category is saved to database
            serializer.save()
            # if success return:
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        # otherwise return:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class ProductCategoryListAPIView(generics.ListAPIView):
    permission_classes = [AllowAny]
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer

@api_view(['PUT'])
@permission_classes([IsAuthenticated, IsProducer])
def update_low_stock_threshold(request, product_id):
    """Update low stock threshold for a product"""
    try:
        product = Product.objects.get(product_id=product_id, producer__user=request.user)
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=404)
    
    threshold = request.data.get('low_stock_threshold')
    if threshold is None:
        return Response({'error': 'Threshold value required'}, status=400)
    
    try:
        threshold = int(threshold)
        if threshold < 0:
            raise ValueError
    except ValueError:
        return Response({'error': 'Threshold must be a positive integer'}, status=400)
    
    product.low_stock_threshold = threshold
    product.save()
    
    from producers.low_stock_service import check_low_stock
    check_low_stock(product)
    
    return Response({
        'success': True,
        'product_id': product.product_id,
        'name': product.name,
        'low_stock_threshold': product.low_stock_threshold
    })