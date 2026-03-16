
from django.shortcuts import render, get_object_or_404, redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Product, ProductCategory, ProductAllergen
from .serializers import ProductSerializer, ProductCategorySerializer, ProductAllergenSerializer
from rest_framework.permissions import AllowAny
from rest_framework import generics
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from user_accounts.permissions import IsCustomer
from django.contrib.auth.decorators import login_required


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
    
    def get(self,request, category_name):
        # get category object
        category = ProductCategory.objects.filter(category_name__iexact=category_name).first()
        
        # getting all the available products in the category
        products = Product.objects.filter(category=category, availability_status=True)
        
        # convert product object to json
        serializer = ProductSerializer(products, many=True) 
        
        # return category namr and products
        return Response({
            "category": category.category_name,
            "products": serializer.data
            
        }, status=status.HTTP_200_OK)


def category_page(request, category_name):
    
    return render(request, 'categories.html', {'category_name': category_name})

def product_detail(request, product_id):
    
    product = get_object_or_404(Product, product_id=product_id)
    
    return render(request, 'product_detail.html', {'product_id': product_id})


class ProductSearchAPIView(APIView):
    def get(self,request):
        # get search query from url
        query = request.GET.get("q", "")
        # get filter
        filter_value = request.GET.get("filter", "")
        products = Product.objects.filter(availability_status=True)
        # get category
        category = request.GET.get("category")
        
        # filter by category
        if category:
            products = products.filter(category__category_name=category)
        
        # if there is a query then filter products by the product name, producer name, or allergen name e.g., potatoes (name)
        # milk (allergen)
        # if a product is out of stock it wont be displayed even when a user tries to search for it using the search bar
        
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
                
            # if a query has multip;le words search description
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
          
        # convert products to json  
        serializer = ProductSerializer(products, many=True)
        
        # return products
        return Response({
    
            "products": serializer.data
            
        }, status=status.HTTP_200_OK)



class ProductDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    
    def get(self, request, product_id):
        # getting product based on primary key
        product = get_object_or_404(Product, pk=product_id)
        
        serializer = ProductSerializer(product)
        #getting all the allergens for the product
        allergens = product.productallergen_set.all()
        allergens_serializer = ProductAllergenSerializer(allergens, many=True)
        
        
        return Response({"product": serializer.data, "allergens": allergens_serializer.data}, status=status.HTTP_200_OK)


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
    
    
