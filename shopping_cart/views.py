from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import ShoppingCart, ShoppingCartItem
from product.models import Product
from django.shortcuts import redirect, get_object_or_404
from .models import ShoppingCart, ShoppingCartItem
from product.models import Product




from django.shortcuts import render, redirect

def cart_page(request):
    return render(request, 'shopping_cart/cart.html')

def add_to_cart(request, product_id):
    # Your logic here
    return redirect('shopping_cart:cart_page')

def update_quantity(request, item_id):
    # Your logic here
    return redirect('shopping_cart:cart_page')

def remove_item(request, item_id):
    # Your logic here
    return redirect('shopping_cart:cart_page')



class CartAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart = ShoppingCart.objects.filter(user=request.user, cart_status="active").first()
        if not cart:
            return Response({"items": [], "total": 0})
        items = cart.items.all()
        data = []
        total = 0
        for item in items:
            data.append({
                "item_id": item.cart_item_id,
                "product_id": item.product.product_id,
                "name": item.product.name,
                "price": float(item.unit_price),
                "quantity": item.quantity,
            })
            total += item.unit_price * item.quantity
        return Response({"items": data, "total": total})



    def add_to_cart(request, product_id):
        if not request.user.is_authenticated:
            return redirect('login')  # redirect if user not logged in

        # Get the product or return 404 if not found
        product = get_object_or_404(Product, product_id=product_id)

        # Get or create the active cart for this user
        cart, _ = ShoppingCart.objects.get_or_create(user=request.user, cart_status="active")

        # Add product to cart or increase quantity if already exists
        item, created = ShoppingCartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': 1, 'unit_price': product.price}
        )
        if not created:
            item.quantity += 1
            item.save()

        return redirect('shopping_cart:cart_page')

class UpdateCartItemAPI(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, item_id):
        action = request.data.get("action")
        item = ShoppingCartItem.objects.filter(cart_item_id=item_id, cart__user=request.user).first()
        if not item:
            return Response({"error": "Item not found"}, status=status.HTTP_404_NOT_FOUND)
        if action == "increase":
            item.quantity += 1
        elif action == "decrease" and item.quantity > 1:
            item.quantity -= 1
        item.save()
        return Response({"message": "Quantity updated"}, status=status.HTTP_200_OK)

class DeleteCartItemAPI(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, item_id):
        item = ShoppingCartItem.objects.filter(cart_item_id=item_id, cart__user=request.user).first()
        if not item:
            return Response({"error": "Item not found"}, status=status.HTTP_404_NOT_FOUND)
        item.delete()
        return Response({"message": "Item removed"}, status=status.HTTP_200_OK)