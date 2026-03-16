from django.shortcuts import render, get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Product, ProductCategory, ProductAllergen
from .serializers import ProductCategorySerializer, ProductCreateSerializer, ProductAllergenSerializer
from rest_framework.permissions import AllowAny
from rest_framework import generics
from django.db.models import Q 


# product home page
def home(request):
    # getting all the categories stored in the database
    categories = ProductCategory.objects.all()
    # debug to check categories
    print("categories in db:", [c.category_name for c in categories])
    
    # getting the query from the url
    query = request.GET.get("q")
    products = None
    # if there is a query then filter products by the product name or allergen name e.g., potatoes (name)
    # milk (allergen)
    # if a product is out of stock it wont be displayed even when a user tries to search for it using the search bar
    if query:
        products = Product.objects.filter(
        availability_status=True).filter(
            Q(name__icontains=query) | Q(allergens__name__icontains=query)
            ).distinct()
        
    # mapping the category names to their corresponding images
    category_images = {
        "Vegetables": "images/carrot.png",
        "Dairy": "images/milk.png",
        "Bakery": "images/bread.png",
        "Preserves": "images/jam-jar.png",
        "Seasonal Specialities": "images/pumpkin.png"
    }
    
    for c in categories:
        c.image_path = category_images.get(c.category_name, "")
       
    # sending data the the template
    return render(request, "product.html", {"categories": categories, "products": products, "query": query} )

# THESE PAGES ARENT DONE YET
def orders(request):
    return render(request, "orders.html")

def about_us(request):
    return render(request, "about_us.html")


def products_category(request, category_name):
    # get category object
    category = get_object_or_404(ProductCategory, category_name=category_name)
    
    # getting all the products in the category
    products = Product.objects.filter(category=category, availability_status=True)
    
    # getting search query
    query = request.GET.get("q")
    if query:
        # filter based on the user query
        products = products.filter(
            Q(name__icontains=query) | Q(allergens__name__icontains=query)
            ).distinct()
        
    
    context = {
        "category": category,
        "products": products,
        "query": query,
    }
    
    return render(request, "categories.html", context)



def product_detail(request, product_id):
    # getting product based on primary key
    product = get_object_or_404(Product, pk=product_id)
    
    #getting all the allergens for the product
    allergens = product.allergens.all()
    
    # sending the product and allergen data to the template
    context = {
        "product": product,
        "allergens": allergens
    }
    
    return render(request, "product_detail.html", context)




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
    
    
# api end point for creating a new product
class  ProductCreateAPIView(generics.CreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductCreateSerializer
    permission_classes = [AllowAny]
    
    # youre going to need this so that when a product is added it is linked to the producer loggedin 
    #def perform_create(self,serializer):
        #serializer.save(producer=self.request.user)
        

# api end point for creating a new allergen
        
class ProductAllergenCreateAPIView(generics.CreateAPIView):
    queryset = ProductAllergen.objects.all()
    serializer_class = ProductAllergenSerializer
    permission_classes= [AllowAny]
    
    
