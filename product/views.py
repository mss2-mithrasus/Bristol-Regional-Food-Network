from django.shortcuts import render, get_object_or_404
from .models import Product, ProductCategory

# Create your views here.
def home(request):
    categories = ProductCategory.objects.all()
    
    context = {
        "categories": categories
    }
    
    
    return render(request, "product.html", context)

def orders(request):
    return render(request, "orders.html")

def about_us(request):
    return render(request, "about_us.html")


def products_category(request, category_name):
    # get category object
    category = get_object_or_404(ProductCategory, category_name=category_name)
    
    # getting all the products in the category
    products = Product.objects.filter(category=category, availability_status=True)
    
    
    context = {
        "category": category,
        "products": products
    }
    
    return render(request, "categories.html", context)