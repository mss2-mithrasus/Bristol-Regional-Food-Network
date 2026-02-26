from django.shortcuts import render

# Create your views here.
def home(request):
    return render(request, "product.html")

def orders(request):
    return render(request, "orders.html")

def about_us(request):
    return render(request, "about_us.html")