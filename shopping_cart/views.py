from django.shortcuts import render
from django.http import JsonResponse
from django.db import transaction
import json

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Cart, CartItem
from product.models import Product
from .serializers import CartSerializer, AddToCartSerializer, UpdateCartItemSerializer

def cart_view(request):
    """
    Display shopping cart page
    """
    if request.method not in ['GET', 'POST']:
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['GET', 'POST'])
    user = None
    token_from_url = request.GET.get('token') or request.POST.get('token')
    
    if token_from_url:
        try:
            from rest_framework_simplejwt.authentication import JWTAuthentication
            from rest_framework_simplejwt.tokens import AccessToken
            from rest_framework.exceptions import AuthenticationFailed
            
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token_from_url)
            user = jwt_auth.get_user(validated_token)
            print(f" Token auth successful: {user.email}")
        except Exception:
            print(" Token auth failed or expired")
    
    # If no user from token, try session
    if not user and request.user.is_authenticated:
        user = request.user
        print(f" Session auth: {user.email}")
    
    # Check if we have a user
    if not user:
        print(" No authenticated user")
        return render(request, 'shopping_cart.html', {'login_required': True})
    
    print(f" Using user: {user.email} (ID: {user.id})")
    
    # Get or create cart for this user
    cart, created = Cart.objects.get_or_create(customer=user)
    print(f" Cart ID: {cart.cart_id}, Created: {created}")
    
    # Get all cart items
    cart_items = cart.items.select_related('product__producer').all()
    items_count = cart_items.count()
    print(f" Cart items count: {items_count}")
    
    # If no items, return empty cart
    if items_count == 0:
        print(" No items in cart")
        context = {
            'cart': cart,
            'cart_items': [],
            'producers': [],
            'subtotal': 0,
            'total_items': 0,
            'has_items': False,
            'tc_006_demo': True,
        }
        return render(request, 'shopping_cart.html', context)
    
    # Process items...
    cart_items_list = list(cart_items)
    
    for item in cart_items_list:
        print(f"  - {item.product.name} x {item.quantity} = £{item.subtotal}")
    
    # Calculate totals
    subtotal = sum(item.quantity * item.product.price for item in cart_items_list)
    subtotal_float = float(subtotal)
    network_fee = round(subtotal_float * 0.05, 2)  # Calculate 5% commission
    total = round(subtotal_float + network_fee, 2)  # Calculate total including fee
    # Group by producer
    producers = []
    producer_dict = {}
    
    for item in cart_items_list:
        producer_name = item.producer_name
        if producer_name not in producer_dict:
            producer_dict[producer_name] = {
                'name': producer_name,
                'items': [],
                'subtotal': 0
            }
        
        producer_dict[producer_name]['items'].append(item)
        producer_dict[producer_name]['subtotal'] += item.subtotal
    
    producers = list(producer_dict.values())
    
    context = {
        'cart': cart,
        'cart_items': cart_items_list,
        'producers': producers,
        'subtotal': subtotal,
        'network_fee': network_fee,
        'total': total,
        'total_items': cart.total_items,
        'has_items': items_count > 0,
        'tc_006_demo': True,
    }
    
    print(f" Context cart_items length: {len(context['cart_items'])}")
    
    return render(request, 'shopping_cart.html', context)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def add_to_cart(request):
    """
    API endpoint to add item to cart
    """
    print(f" ADD TO CART - User: {request.user.email}")
    print(f" ADD TO CART - User ID: {request.user.id}")
    print(f" ADD TO CART - Auth: {request.auth}")
    serializer = AddToCartSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    product_id = serializer.validated_data['product_id']
    quantity = serializer.validated_data['quantity']
    
    try:
        product = Product.objects.get(product_id=product_id, availability_status=True)
    except Product.DoesNotExist:
        return Response(
            {'error': 'Product not found or unavailable'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check stock availability
    if product.stock_quantity < quantity:
        return Response(
            {'error': f'Only {product.stock_quantity} available in stock'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get or create cart for user
    cart, _ = Cart.objects.get_or_create(customer=request.user)
    
    print(f" ADD TO CART - Using cart ID: {cart.cart_id}")
    print(f" ADD TO CART - Cart belongs to: {cart.customer.email}")
    print(f" ADD TO CART - Cart belongs to user ID: {cart.customer.id}")
    
    # Check if item already in cart
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': quantity}
    )
    
    if not created:
        # Update quantity if item already exists
        new_quantity = cart_item.quantity + quantity
        if new_quantity > product.stock_quantity:
            return Response(
                {'error': f'Cannot add more than {product.stock_quantity} items'},
                status=status.HTTP_400_BAD_REQUEST
            )
        cart_item.quantity = new_quantity
        cart_item.save()
    
    # Return updated cart data
    cart_serializer = CartSerializer(cart)
    
    return Response({
        'success': True,
        'message': f'{quantity} x {product.name} added to cart',
        'cart': cart_serializer.data,
        'cart_total_items': cart.total_items,
        'cart_subtotal': float(cart.subtotal)
    }, status=status.HTTP_200_OK)
    
@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def update_cart_item(request, item_id):
    try:
        cart_item = CartItem.objects.get(
            cart_item_id=item_id,
            cart__customer=request.user
        )
    except CartItem.DoesNotExist:
        return Response(
            {'error': 'Cart item not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'DELETE':
        # Remove item from cart
        product_name = cart_item.product.name
        cart_item.delete()
        
        # Get updated cart
        cart = Cart.objects.get(customer=request.user)
        cart_serializer = CartSerializer(cart)
        
        return Response({
            'success': True,
            'message': f'{product_name} removed from cart',
            'cart': cart_serializer.data,
            'cart_total_items': cart.total_items,
            'cart_subtotal': float(cart.subtotal)
        }, status=status.HTTP_200_OK)
    
    elif request.method == 'PUT':
        # Update quantity
        serializer = UpdateCartItemSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        new_quantity = serializer.validated_data['quantity']
        
        if new_quantity == 0:
            # Remove item if quantity is 0
            product_name = cart_item.product.name
            cart_item.delete()
            
            cart = Cart.objects.get(customer=request.user)
            cart_serializer = CartSerializer(cart)
            
            return Response({
                'success': True,
                'message': f'{product_name} removed from cart',
                'cart': cart_serializer.data,
                'cart_total_items': cart.total_items,
                'cart_subtotal': float(cart.subtotal)
            }, status=status.HTTP_200_OK)
        
        # Check stock
        if new_quantity > cart_item.product.stock_quantity:
            return Response(
                {'error': f'Only {cart_item.product.stock_quantity} available'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update quantity
        cart_item.quantity = new_quantity
        cart_item.save()
        
        # Get updated cart
        cart = Cart.objects.get(customer=request.user)
        cart_serializer = CartSerializer(cart)
        
        # Calculate new item subtotal
        new_subtotal = cart_item.quantity * cart_item.product.price
        
        return Response({
            'success': True,
            'message': f'Quantity updated to {new_quantity}',
            'cart': cart_serializer.data,
            'cart_total_items': cart.total_items,
            'cart_subtotal': float(cart.subtotal),
            'item_subtotal': float(new_subtotal)
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cart_data(request):
    """
    Get cart data as JSON (for AJAX updates)
    """
    cart, _ = Cart.objects.get_or_create(customer=request.user)
    serializer = CartSerializer(cart)
    
    return Response({
        'cart': serializer.data,
        'total_items': cart.total_items,
        'subtotal': float(cart.subtotal)
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cart_icon_data(request):
    print(f" CART ICON - User: {request.user.email}")
    print(f" CART ICON - User ID: {request.user.id}")

    cart, _ = Cart.objects.get_or_create(customer=request.user)
    return Response({
        'total_items': cart.total_items,
        'subtotal': float(cart.subtotal)
    })

from django.http import JsonResponse
from django.db import transaction
import json

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Cart, CartItem
from product.models import Product
from .serializers import CartSerializer, AddToCartSerializer, UpdateCartItemSerializer

def cart_view(request):
    """
    Display shopping cart page
    """
    if request.method not in ['GET', 'POST']:
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['GET', 'POST'])
    user = None
    token_from_url = request.GET.get('token') or request.POST.get('token')
    
    if token_from_url:
        try:
            from rest_framework_simplejwt.authentication import JWTAuthentication
            from rest_framework_simplejwt.tokens import AccessToken
            from rest_framework.exceptions import AuthenticationFailed
            
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token_from_url)
            user = jwt_auth.get_user(validated_token)
            print(f" Token auth successful: {user.email}")
        except Exception:
            print(" Token auth failed or expired")
    
    # If no user from token, try session
    if not user and request.user.is_authenticated:
        user = request.user
        print(f" Session auth: {user.email}")
    
    # Check if we have a user
    if not user:
        print(" No authenticated user")
        return render(request, 'shopping_cart.html', {'login_required': True})
    
    print(f" Using user: {user.email} (ID: {user.id})")
    
    # Get or create cart for this user
    cart, created = Cart.objects.get_or_create(customer=user)
    print(f" Cart ID: {cart.cart_id}, Created: {created}")
    
    # Get all cart items
    cart_items = cart.items.select_related('product__producer').all()
    items_count = cart_items.count()
    print(f" Cart items count: {items_count}")
    
    # If no items, return empty cart
    if items_count == 0:
        print(" No items in cart")
        context = {
            'cart': cart,
            'cart_items': [],
            'producers': [],
            'subtotal': 0,
            'total_items': 0,
            'has_items': False,
            'tc_006_demo': True,
        }
        return render(request, 'shopping_cart.html', context)
    
    # Process items...
    cart_items_list = list(cart_items)
    
    for item in cart_items_list:
        print(f"  - {item.product.name} x {item.quantity} = £{item.subtotal}")
    
    # Calculate totals
    subtotal = sum(item.quantity * item.product.price for item in cart_items_list)
    subtotal_float = float(subtotal)
    network_fee = round(subtotal_float * 0.05, 2)  # Calculate 5% commission
    total = round(subtotal_float + network_fee, 2)  # Calculate total including fee
    # Group by producer
    producers = []
    producer_dict = {}
    
    for item in cart_items_list:
        producer_name = item.producer_name
        if producer_name not in producer_dict:
            producer_dict[producer_name] = {
                'name': producer_name,
                'items': [],
                'subtotal': 0
            }
        
        producer_dict[producer_name]['items'].append(item)
        producer_dict[producer_name]['subtotal'] += item.subtotal
    
    producers = list(producer_dict.values())
    
    context = {
        'cart': cart,
        'cart_items': cart_items_list,
        'producers': producers,
        'subtotal': subtotal,
        'network_fee': network_fee,
        'total': total,
        'total_items': cart.total_items,
        'has_items': items_count > 0,
        'tc_006_demo': True,
    }
    
    print(f" Context cart_items length: {len(context['cart_items'])}")
    
    return render(request, 'shopping_cart.html', context)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def add_to_cart(request):
    """
    API endpoint to add item to cart
    """
    print(f" ADD TO CART - User: {request.user.email}")
    print(f" ADD TO CART - User ID: {request.user.id}")
    print(f" ADD TO CART - Auth: {request.auth}")
    serializer = AddToCartSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    product_id = serializer.validated_data['product_id']
    quantity = serializer.validated_data['quantity']
    
    try:
        product = Product.objects.get(product_id=product_id, availability_status=True)
    except Product.DoesNotExist:
        return Response(
            {'error': 'Product not found or unavailable'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check stock availability
    if product.stock_quantity < quantity:
        return Response(
            {'error': f'Only {product.stock_quantity} available in stock'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get or create cart for user
    cart, _ = Cart.objects.get_or_create(customer=request.user)
    
    print(f" ADD TO CART - Using cart ID: {cart.cart_id}")
    print(f" ADD TO CART - Cart belongs to: {cart.customer.email}")
    print(f" ADD TO CART - Cart belongs to user ID: {cart.customer.id}")
    
    # Check if item already in cart
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': quantity}
    )
    
    if not created:
        # Update quantity if item already exists
        new_quantity = cart_item.quantity + quantity
        if new_quantity > product.stock_quantity:
            return Response(
                {'error': f'Cannot add more than {product.stock_quantity} items'},
                status=status.HTTP_400_BAD_REQUEST
            )
        cart_item.quantity = new_quantity
        cart_item.save()
    
    # Return updated cart data
    cart_serializer = CartSerializer(cart)
    
    return Response({
        'success': True,
        'message': f'{quantity} x {product.name} added to cart',
        'cart': cart_serializer.data,
        'cart_total_items': cart.total_items,
        'cart_subtotal': float(cart.subtotal)
    }, status=status.HTTP_200_OK)
    
@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def update_cart_item(request, item_id):
    try:
        cart_item = CartItem.objects.get(
            cart_item_id=item_id,
            cart__customer=request.user
        )
    except CartItem.DoesNotExist:
        return Response(
            {'error': 'Cart item not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'DELETE':
        # Remove item from cart
        product_name = cart_item.product.name
        cart_item.delete()
        
        # Get updated cart
        cart = Cart.objects.get(customer=request.user)
        cart_serializer = CartSerializer(cart)
        
        return Response({
            'success': True,
            'message': f'{product_name} removed from cart',
            'cart': cart_serializer.data,
            'cart_total_items': cart.total_items,
            'cart_subtotal': float(cart.subtotal)
        }, status=status.HTTP_200_OK)
    
    elif request.method == 'PUT':
        # Update quantity
        serializer = UpdateCartItemSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        new_quantity = serializer.validated_data['quantity']
        
        if new_quantity == 0:
            # Remove item if quantity is 0
            product_name = cart_item.product.name
            cart_item.delete()
            
            cart = Cart.objects.get(customer=request.user)
            cart_serializer = CartSerializer(cart)
            
            return Response({
                'success': True,
                'message': f'{product_name} removed from cart',
                'cart': cart_serializer.data,
                'cart_total_items': cart.total_items,
                'cart_subtotal': float(cart.subtotal)
            }, status=status.HTTP_200_OK)
        
        # Check stock
        if new_quantity > cart_item.product.stock_quantity:
            return Response(
                {'error': f'Only {cart_item.product.stock_quantity} available'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update quantity
        cart_item.quantity = new_quantity
        cart_item.save()
        
        # Get updated cart
        cart = Cart.objects.get(customer=request.user)
        cart_serializer = CartSerializer(cart)
        
        # Calculate new item subtotal
        new_subtotal = cart_item.quantity * cart_item.product.price
        
        return Response({
            'success': True,
            'message': f'Quantity updated to {new_quantity}',
            'cart': cart_serializer.data,
            'cart_total_items': cart.total_items,
            'cart_subtotal': float(cart.subtotal),
            'item_subtotal': float(new_subtotal)
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cart_data(request):
    """
    Get cart data as JSON (for AJAX updates)
    """
    cart, _ = Cart.objects.get_or_create(customer=request.user)
    serializer = CartSerializer(cart)
    
    return Response({
        'cart': serializer.data,
        'total_items': cart.total_items,
        'subtotal': float(cart.subtotal)
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cart_icon_data(request):
    print(f" CART ICON - User: {request.user.email}")
    print(f" CART ICON - User ID: {request.user.id}")

    cart, _ = Cart.objects.get_or_create(customer=request.user)
    return Response({
        'total_items': cart.total_items,
        'subtotal': float(cart.subtotal)
    })