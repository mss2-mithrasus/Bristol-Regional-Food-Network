from django.shortcuts import render, redirect
from django.db import connection
from .models import ShoppingCart, ShoppingCartItem, Product


# -----------------------------
# HOME PAGE (optional)
# -----------------------------
def home(request):
    return render(request, "home.html")   # or your landing page template


# -----------------------------
# PRODUCTS PAGE
# -----------------------------
def products_page(request):
    # Load all products from the Product table
    products = Product.objects.all()
    return render(request, "products.html", {"products": products})


# -----------------------------
# ADD TO CART
# -----------------------------
def add_to_cart(request, product_id):

    #  Get or create the user's active cart
    cart, created = ShoppingCart.objects.get_or_create(
        user_id=request.user.id,
        cart_status="active"
    )

    #  Get the product from DB
    product = Product.objects.get(id=product_id)

    #  Add or update the cart item
    item, created = ShoppingCartItem.objects.get_or_create(
        cart_id=cart.cart_id,
        product_id=product_id,
        defaults={"quantity": 1, "unit_price": product.price}
    )

    if not created:
        item.quantity += 1
        item.save()

    return redirect("cart_page")


# -----------------------------
# CART PAGE
# -----------------------------
def cart_page(request):

    # Get the user's active cart
    cart = ShoppingCart.objects.filter(
        user_id=request.user.id,
        cart_status="active"
    ).first()

    if not cart:
        return render(request, "cart.html", {"items": [], "total": 0})

    # Get all items in the cart
    items = ShoppingCartItem.objects.filter(cart_id=cart.cart_id)

    # Calculate total
    total = sum(i.unit_price * i.quantity for i in items)

    return render(request, "cart.html", {"items": items, "total": total})


# -----------------------------
# UPDATE QUANTITY
# -----------------------------
def update_quantity(request, item_id):
    item = ShoppingCartItem.objects.get(cart_item_id=item_id)
    action = request.POST.get("action")

    if action == "increase":
        item.quantity += 1
    elif action == "decrease" and item.quantity > 1:
        item.quantity -= 1

    item.save()
    return redirect("cart_page")


# -----------------------------
# REMOVE ITEM
# -----------------------------
def remove_item(request, item_id):
    ShoppingCartItem.objects.filter(cart_item_id=item_id).delete()
    return redirect("cart_page")