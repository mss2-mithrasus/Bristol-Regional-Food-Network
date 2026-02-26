from django.shortcuts import render
from django.http import HttpResponse
from django.db import connection
from django.contrib.auth.decorators import login_required
from product.models import Product
def db_test(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES;")
            tables = cursor.fetchall()
        return HttpResponse(f"Database OK — Tables: {tables}")
    except Exception as e:
        return HttpResponse(f"Database ERROR: {e}")
    

def dashboard(request):
    return render(request, "dashboard.html")
def product_management(request):
    return render(request, "product_management.html")

def add_product(request):
    return render(request, "add_product.html")