from django.shortcuts import render
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .utils import get_available_stock
from product.models import Product
import json

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Q 
from decimal import Decimal, ROUND_HALF_UP

from .models import Cart, CartItem
from product.models import Product
from .serializers import CartSerializer, AddToCartSerializer, UpdateCartItemSerializer
from producers.models import SurplusDiscount
from producers.utils import is_product_valid_for_fulfilment, get_earliest_fulfilment_date

def check_and_notify_stock_available(product):
    """Check if product now has available stock and notify waiting customers"""
    from .utils import get_available_stock
    # Count ALL active reservations
    total_reserved = CartItem.objects.filter(
        product=product,
        reserved_until__gt=timezone.now()
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    available = product.stock_quantity - total_reserved
    
    
    if available > 0:
        try:
            from notifications.utils import notify_stock_available
            notified = notify_stock_available(product)
            return notified
        except ImportError as e:
            print(f" Notification import error: {e}")
    return 0

def block_if_product_not_fulfillable(product):
    """
    Block products that cannot be fulfilled.

    Cases:
    - already past best before date -> mark expired/unavailable and expire surplus deals
    - before earliest fulfilment date -> mark unavailable and cancel active surplus deals
    """
    today = timezone.now().date()
    earliest_fulfilment_date = get_earliest_fulfilment_date()

    if product.best_before_date:
        # Truly expired
        if product.best_before_date < today:
            product.availability_status = False
            product.is_expired = True
            product.save(update_fields=["availability_status", "is_expired"])

            SurplusDiscount.objects.filter(
                product=product,
                status="active"
            ).update(status="expired")

            return True

        # Not expired yet, but cannot be fulfilled in time
        if product.best_before_date < earliest_fulfilment_date:
            SurplusDiscount.objects.filter(
                product=product,
                status="active"
            ).update(status="cancelled")

            return True
        # if product.best_before_date < earliest_fulfilment_date:
        #     if product.availability_status:
        #         product.availability_status = False
        #         product.save(update_fields=["availability_status"])

        #     SurplusDiscount.objects.filter(
        #         product=product,
        #         status="active"
        #     ).update(status="cancelled")

        #     return True

    return False

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
    
    # Check if we have a user
    if not user:
        print(" No authenticated user")
        return render(request, 'shopping_cart.html', {'login_required': True})
    
    print(f" Using user: {user.email} (ID: {user.id})")
    
    # Get or create cart for this user
    cart, created = Cart.objects.get_or_create(customer=user)
    # Clean up expired items for this user
    now = timezone.now()
    expired_items = cart.items.filter(reserved_until__lt=now).select_related('product')
    expired_count = expired_items.count()
    if expired_count > 0:
        expired_products = list(set([item.product for item in expired_items]))
        expired_items.delete()
        for product in expired_products:
            check_and_notify_stock_available(product)
    print(f" Cart ID: {cart.cart_id}, Created: {created}")
    
    # Get all cart items
    cart_items = cart.items.select_related('product__producer').all()
    
    # Removed items from cart f they r expired after adding to the cart
    invalid_cart_items = []

    for item in cart_items:
        product = item.product

        if (
            block_if_product_not_fulfillable(product)
            or product.stock_quantity <= 0
            or not product.availability_status
        ):
            invalid_cart_items.append(item)

    if invalid_cart_items:
        for item in invalid_cart_items:
            item.delete()

        cart_items = cart.items.select_related('product__producer').all()
    items_count = cart_items.count()
    
    
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
    #subtotal = sum(item.quantity * item.product.price for item in cart_items_list)
    # Micaiah changed for surplus discount
    subtotal = sum(item.subtotal for item in cart_items_list)
    subtotal_float = float(subtotal)
    network_fee = round(subtotal_float * 0.05, 2)  # Calculate 5% commission
    total = subtotal_float  # Total to pay is same as subtotal (commission already included)
    # Group by producer
    producers = []
    producer_dict = {}
    
    #felna added - account tye for bulk discount
    try:
        account_type = request.user.customeraccount.account_type
    except Exception:
        account_type = "normal" # ended
    total_bulk_savings = Decimal('0')

    for item in cart_items_list:
        surplus_unit_price = Decimal(str(item.unit_price))
        surplus_line_total = (surplus_unit_price * item.quantity).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        producer = item.product.producer
        has_surplus = surplus_unit_price != Decimal(str(item.product.price))
        bulk_applies = (
            not has_surplus
            and producer.is_bulk_eligible_for(account_type)
            and item.quantity >= producer.bulk_threshold_quantity
        )

        if bulk_applies:
            bulk_pct = Decimal(str(producer.bulk_discount_percentage))
            final_unit_price = (
                surplus_unit_price * (Decimal("1") - bulk_pct / Decimal("100"))
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            final_line_total = (final_unit_price * item.quantity).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            line_bulk_savings = surplus_line_total - final_line_total
        else:
            bulk_pct = Decimal("0")
            final_unit_price = surplus_unit_price
            final_line_total = surplus_line_total
            line_bulk_savings = Decimal("0")

        # Attach computed values to the item so the template can read them
        item.surplus_unit_price = surplus_unit_price
        item.surplus_line_total = surplus_line_total
        item.final_unit_price = final_unit_price
        item.final_line_total = final_line_total
        item.bulk_applied = bulk_applies
        item.bulk_pct = bulk_pct
        item.line_bulk_savings = line_bulk_savings

        total_bulk_savings += line_bulk_savings

        # Group by producer
        producer_name = item.producer_name
        if producer_name not in producer_dict:
            producer_dict[producer_name] = {
                "name": producer_name,
                "items": [],
                "subtotal": Decimal("0"),             # before bulk (surplus already applied)
                "discounted_subtotal": Decimal("0"),  # after bulk
                "bulk_discount_amount": Decimal("0"),
                "has_bulk_discount": False,
            }

        producer_dict[producer_name]["items"].append(item)
        producer_dict[producer_name]["subtotal"] += surplus_line_total
        producer_dict[producer_name]["discounted_subtotal"] += final_line_total
        producer_dict[producer_name]["bulk_discount_amount"] += line_bulk_savings
        if bulk_applies:
            producer_dict[producer_name]["has_bulk_discount"] = True

    producers = list(producer_dict.values())

    # Cart totals based on discounted (final) subtotals
    subtotal = sum((g["discounted_subtotal"] for g in producers), Decimal("0"))
    subtotal_float = float(subtotal)
    network_fee = round(subtotal_float * 0.05, 2)
    total = subtotal_float
    # end felna
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
        'total_bulk_savings': total_bulk_savings,
        'account_type': account_type,
        'is_bulk_account': account_type in ['community', 'restaurant'],
    }
    
    
    return render(request, 'shopping_cart.html', context)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def add_to_cart(request):
    """
    API endpoint to add item to cart
    """
    
    serializer = AddToCartSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    product_id = serializer.validated_data['product_id']
    requested_quantity = serializer.validated_data['quantity']
    
    viewed = request.session.get(f"viewed_{product_id}")
    
    if not viewed:
        return Response(
            {
                'success': False,
                'error': 'Please view product details for allergen information before adding to cart'
            },
            status=status.HTTP_403_FORBIDDEN
        )
    
    # try:
    #     product = Product.objects.select_for_update().get(
    #         product_id=product_id, 
    #         availability_status=True
    #     )
    # except Product.DoesNotExist:
    #     return Response(
    #         {'error': 'Product not found or unavailable'},
    #         status=status.HTTP_404_NOT_FOUND
    #     )

    try:
        product = Product.objects.select_for_update().get(product_id=product_id)
    except Product.DoesNotExist:
        return Response(
            {'error': 'Product not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if block_if_product_not_fulfillable(product):
        earliest_fulfilment_date = get_earliest_fulfilment_date()

        if product.best_before_date and product.best_before_date < timezone.now().date():
            error_message = "This product has passed its best before date and can no longer be purchased."
        else:
            error_message = (
                f"This product cannot be purchased because its best before date is earlier "
                f"than the earliest fulfilment date ({earliest_fulfilment_date.strftime('%d %b %Y')})."
            )

        return Response(
            {
                'success': False,
                'error': error_message
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if not is_product_valid_for_fulfilment(product):
        return Response(
            {
                'success': False,
                'error': 'This product is not available for fulfilment.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if not product.availability_status:
        return Response(
            {'error': 'Product not found or unavailable'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get or create cart for user
    cart, _ = Cart.objects.get_or_create(customer=request.user)
    
    # Calculate what's available for THIS user to add
    # First, get ALL active reservations from OTHER users
    other_users_reservations = CartItem.objects.filter(
        product=product,
        reserved_until__gt=timezone.now()
    ).exclude(
        cart__customer=request.user
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    print(f" Other users have reserved: {other_users_reservations}")
    
    # Calculate what this user already has in their cart
    user_cart_item = CartItem.objects.filter(
        cart=cart,
        product=product
    ).first()
    
    user_current_quantity = user_cart_item.quantity if user_cart_item else 0
    print(f" User already has: {user_current_quantity} in cart")
    
    # Available for this user to add = total stock - other users' reservations - user's current
    available_to_add = product.stock_quantity - other_users_reservations - user_current_quantity
    print(f" Available for user to add: {available_to_add}")
    
    # Check if requested quantity is available
    if requested_quantity > available_to_add:
        if user_current_quantity == 0:
            error_msg = f'Sorry, only {available_to_add} items available in stock.'
        else:
            error_msg = f'You already have {user_current_quantity} in your cart. Only {available_to_add} more available.'
    
        return Response({
            'success': False,
            'error': error_msg
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Set reservation expiry (30 minutes from now)
    reservation_expiry = timezone.now() + timedelta(minutes=30)
    
    if user_cart_item:
        # Update existing cart item
        user_cart_item.quantity += requested_quantity
        user_cart_item.reserved_until = reservation_expiry
        user_cart_item.save()
    else:
        # Create new cart item
        CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=requested_quantity,
            reserved_until=reservation_expiry
        )
    from producers.low_stock_service import check_low_stock
    check_low_stock(product)
    # Return updated cart data
    cart_serializer = CartSerializer(cart)
    
    return Response({
        'success': True,
        'message': f'{requested_quantity} x {product.name} added to cart',
        'cart': cart_serializer.data,
        'cart_total_items': cart.total_items,
        'cart_subtotal': float(cart.subtotal)
    }, status=status.HTTP_200_OK)
    
@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def update_cart_item(request, item_id):
    try:
        cart_item = CartItem.objects.select_related('product').get(
            cart_item_id=item_id,
            cart__customer=request.user
        )
    except CartItem.DoesNotExist:
        return Response(
            {'error': 'Cart item not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    product = cart_item.product
    if not product.availability_status:
        cart_item.delete()
        return Response(
            {
                'success': False,
                'error': 'This product is no longer available and has been removed from your cart.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    if block_if_product_not_fulfillable(product):
        earliest_fulfilment_date = get_earliest_fulfilment_date()

        if product.best_before_date and product.best_before_date < timezone.now().date():
            error_message = 'This product has passed its best before date and can no longer remain in the cart.'
        else:
            error_message = (
                f'This product can no longer remain in the cart because its best before date '
                f'is earlier than the earliest fulfilment date ({earliest_fulfilment_date.strftime("%d %b %Y")}).'
            )

        cart_item.delete()

        return Response(
            {
                'success': False,
                'error': error_message
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    if request.method == 'DELETE':
        # Remove item from cart
        product_name = cart_item.product.name
        product_to_check = cart_item.product
        cart_item.delete()
        # Notify AFTER transaction commits so stock counts are accurate
        transaction.on_commit(lambda: check_and_notify_stock_available(product_to_check))
        # Get updated cart
        cart = Cart.objects.get(customer=request.user)
        cart_serializer = CartSerializer(cart)
        
        return Response({
            'success': True,
            'message': f'{product_name} removed from cart (stock released)',
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
            product_to_check = cart_item.product
            cart_item.delete()
            # Check if stock became available
            transaction.on_commit(lambda: check_and_notify_stock_available(product_to_check))
            cart = Cart.objects.get(customer=request.user)
            cart_serializer = CartSerializer(cart)
            
            return Response({
                'success': True,
                'message': f'{product_name} removed from cart',
                'cart': cart_serializer.data,
                'cart_total_items': cart.total_items,
                'cart_subtotal': float(cart.subtotal)
            }, status=status.HTTP_200_OK)
        # Check if new quantity is available
        from .utils import get_available_stock
        available_stock = get_available_stock(product, request.user)
        # Calculate max allowed for this user (their current reservation + available stock)
        max_allowed = cart_item.quantity + available_stock
        print(f"Max allowed for this user: {max_allowed}")
        
        # Check stock
        if new_quantity > max_allowed:
            print(f" BLOCKED: {new_quantity} > {max_allowed}")
            return Response(
                {'error': f'Only {max_allowed} items available (including your current {cart_item.quantity})'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        # Also check against total stock
        if new_quantity > product.stock_quantity:
            print(f" BLOCKED: {new_quantity} > {product.stock_quantity}")
            return Response({
                'error': f'Only {product.stock_quantity} items exist in total'
            }, status=status.HTTP_400_BAD_REQUEST)
        print(f" ALLOWED: Updating to {new_quantity}")
        # Update quantity
        cart_item.quantity = new_quantity
        cart_item.reserved_until = timezone.now() + timedelta(minutes=30)  # Extend reservation
        cart_item.save()
        
        from producers.low_stock_service import check_low_stock
        check_low_stock(product)
        
        # Check if reducing quantity freed up stock for waiting customers
        transaction.on_commit(lambda: check_and_notify_stock_available(product))
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
    # Clean up expired items
    now = timezone.now()
    cart.items.filter(reserved_until__lt=now).delete()
    serializer = CartSerializer(cart)
    
    return Response({
        'cart': serializer.data,
        'total_items': cart.total_items,
        'subtotal': float(cart.subtotal)
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cart_item_available_stock(request, item_id):
    """
    Get real-time available stock for a cart item (considering other users' reservations)
    """
    try:
        cart_item = CartItem.objects.select_related('product', 'cart').get(
            cart_item_id=item_id,
            cart__customer=request.user
        )
        
        product = cart_item.product
        if not product.availability_status or block_if_product_not_fulfillable(product):
        #if block_if_product_not_fulfillable(product):
            return Response({
                'success': True,
                'item_id': item_id,
                'product_id': product.product_id,
                'product_name': product.name,
                'current_quantity': cart_item.quantity,
                'max_total_allowed': 0,
                'additional_can_add': 0,
                'total_stock': product.stock_quantity,
                'other_users_reserved': 0
            })
        
        other_users_reservations = CartItem.objects.filter(
            product=product,
            reserved_until__gt=timezone.now()
        ).exclude(
            cart__customer=request.user
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        max_total_allowed = product.stock_quantity - other_users_reservations
        
        return Response({
            'success': True,
            'item_id': item_id,
            'product_id': product.product_id,
            'product_name': product.name,
            'current_quantity': cart_item.quantity,
            'max_total_allowed': max_total_allowed,
            'additional_can_add': max(0, max_total_allowed - cart_item.quantity),
            'total_stock': product.stock_quantity,
            'other_users_reserved': other_users_reservations
        })
        
    except CartItem.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Cart item not found'
        }, status=404)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cart_icon_data(request):

    cart, _ = Cart.objects.get_or_create(customer=request.user)
    # Clean up expired items
    now = timezone.now()
    cart.items.filter(reserved_until__lt=now).delete()
    return Response({
        'total_items': cart.total_items,
        'subtotal': float(cart.subtotal)
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_product_availability(request, product_id):
    """Check how many units of a product are available for the current user"""
    # try:
    #     product = Product.objects.get(product_id=product_id)
        
    #     from .utils import get_available_stock
    #     available = get_available_stock(product, exclude_user=request.user)
    try:
        product = Product.objects.get(product_id=product_id)
        if not product.availability_status or block_if_product_not_fulfillable(product):
        #if block_if_product_not_fulfillable(product):
            return Response({
                'success': True,
                'product_id': product_id,
                'available': 0,
                'total_stock': product.stock_quantity,
                'is_available_to_user': False
            })

        from .utils import get_available_stock
        available = get_available_stock(product, exclude_user=request.user) 
        return Response({
            'success': True,
            'product_id': product_id,
            'available': available,
            'total_stock': product.stock_quantity,
            'is_available_to_user': available > 0
        })
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=404)
