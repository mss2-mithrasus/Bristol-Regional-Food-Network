from django.shortcuts import render, redirect, get_object_or_404
from .models import ShoppingCart, ShoppingCartItem
from product.models import Product
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

@login_required
def cart_page(request):
    cart, _ = ShoppingCart.objects.get_or_create(user=request.user, cart_status="active")
    items = []
    total = 0
    for i in cart.items.all():
        items.append({
            "id": i.cart_item_id,
            "product": i.product,
            "quantity": i.quantity,
            "subtotal": i.unit_price * i.quantity,
        })
        total += i.unit_price * i.quantity
    return render(request, "shopping_cart/cart.html", {"items": items, "total": total})

@login_required
@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, product_id=product_id)
    cart, _ = ShoppingCart.objects.get_or_create(user=request.user, cart_status="active")
    item, created = ShoppingCartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': 1, 'unit_price': product.price}
    )
    if not created:
        item.quantity += 1
        item.save()
    return redirect('shopping_cart:cart_page')

@login_required
@require_POST
def update_quantity(request, item_id, action):
    item = get_object_or_404(ShoppingCartItem, cart_item_id=item_id, cart__user=request.user)
    if action == "increase":
        item.quantity += 1
    elif action == "decrease" and item.quantity > 1:
        item.quantity -= 1
    item.save()
    return redirect('shopping_cart:cart_page')

@login_required
@require_POST
def remove_item(request, item_id):
    item = get_object_or_404(ShoppingCartItem, cart_item_id=item_id, cart__user=request.user)
    item.delete()
    return redirect('shopping_cart:cart_page')