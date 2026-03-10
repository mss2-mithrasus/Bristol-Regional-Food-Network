from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from datetime import timedelta
from user_accounts.models import CustomerAccount, Person, Address, ProducerAccount
from shopping_cart.models import Cart
import logging
import random
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .models import Order, SubOrder, OrderItem

logger = logging.getLogger(__name__)

def order_home(request):
    return render(request, "base.html")


def multi_checkout(request):
    # Get user (similar to cart_view)
    user = None
    if request.user.is_authenticated:
        user = request.user
        print(f" User authenticated: {user.email}")
    else:
        # Handle not logged in - redirect to login
        print(" User not authenticated, redirecting to login")
        return redirect('login')
    
    # Get cart for this user (same as cart_view)
    try:
        cart = Cart.objects.get(customer=user)
        print(f" Cart found: {cart.cart_id}, Items: {cart.total_items}")
    except Cart.DoesNotExist:
        # No cart - empty checkout
        print(" No cart found")
        return render(request, 'multi_checkout.html', {
            'producer_groups': [],
            'total': 0,
            'user_address': None
        })
    
    # Get items grouped by producer using the model method (same as cart_view)
    items_by_producer_dict = cart.get_items_grouped_by_producer()
    print(f" Producers in cart: {len(items_by_producer_dict)}")
    
    # ===== FIX PRODUCER NAMES HERE =====
    # If producer names are "Unknown Producer", try to get them from items
    for producer, data in items_by_producer_dict.items():
        if data['producer_name'] == "Unknown Producer" and data['items']:
            # Get from the first item's producer_name property
            first_item = data['items'][0]
            if hasattr(first_item, 'producer_name'):
                data['producer_name'] = first_item.producer_name
                print(f"Fixed producer name: {data['producer_name']}")
    # ===== END FIX =====
    
    # Calculate 48‑hour minimum delivery date
    min_delivery_date = (timezone.now() + timedelta(hours=48)).date()
    
    # Build producer_groups for template
    producer_groups = []
    overall_subtotal = 0
    total_quantity = 0  # Initialize total quantity counter
    
    for producer, data in items_by_producer_dict.items():
        # Calculate producer totals
        producer_subtotal = float(data['subtotal'])
        producer_commission = round(producer_subtotal * 0.05, 2)
        producer_total = round(producer_subtotal * 1.05, 2)

        # ===== GET PRODUCER ADDRESS (SIMPLIFIED - JUST ADDRESS) =====
        producer_address = None
        try:
            # Check what type 'producer' is and get address accordingly
            if hasattr(producer, 'produceraccount'):
                # producer is a User with produceraccount relation
                producer_account = producer.produceraccount
            elif hasattr(producer, 'address'):
                # producer is already a ProducerAccount
                producer_account = producer
            else:
                # Try to get by user ID
                producer_account = ProducerAccount.objects.get(user=producer)
            
            if producer_account and hasattr(producer_account, 'address') and producer_account.address:
                producer_address = {
                    'street': producer_account.address.address_line,
                    'postcode': producer_account.address.postcode,
                }
        except Exception as e:
            print(f"Error getting producer address: {e}")
            producer_address = None
        # ===== END PRODUCER ADDRESS =====
        
        # Format items for template with MORE DETAILS
        formatted_items = []
        for item in data['items']:
            # Get product details
            product = item.product
            
            # Add to total quantity counter
            total_quantity += item.quantity
            
            # Get image URL if exists
            image_url = None
            if hasattr(product, 'image') and product.image:
                try:
                    image_url = product.image.url
                except:
                    image_url = None
            
            # Get unit if exists
            unit = ''
            if hasattr(product, 'unit') and product.unit:
                unit = product.unit
            
            # Check if organic certified
            organic = False
            if hasattr(product, 'organic_certified'):
                organic = product.organic_certified
            
            formatted_items.append({
                'product': product,
                'product_id': product.product_id if hasattr(product, 'product_id') else product.id,
                'name': product.name,
                'quantity': item.quantity,
                'price': float(product.price),
                'unit': unit,
                'image': image_url,
                'organic_certified': organic,
            })
        
        producer_groups.append({
            "producer": {
                "id": data['producer_id'],
                "name": data['producer_name']  # Now using the fixed name
            },
            "producer_address": producer_address,  # Just street and postcode
            "items": formatted_items,
            "min_delivery_date": min_delivery_date,
            "subtotal": producer_subtotal,
            "commission": producer_commission,
            "total": producer_total,
        })
        
        overall_subtotal += producer_subtotal
    
    overall_total = round(overall_subtotal * 1.05, 2)
    
    # Get user address - SIMPLIFIED - JUST ADDRESS (NO PERSONAL INFO)
    user_address = None
    if user.is_authenticated:
        try:
            customer = CustomerAccount.objects.get(user=user)
            
            # Get address - ONLY address fields, no personal info
            if customer.address:
                street = customer.address.address_line
                postcode = customer.address.postcode
            else:
                street = "No address saved"
                postcode = ""
            
            user_address = {
                'street': street,
                'postcode': postcode,
            }
        except CustomerAccount.DoesNotExist:
            user_address = {
                'street': 'Please create a customer profile',
                'postcode': '',
            }
    
    # After creating producer_groups, create a session-safe copy
    session_producer_groups = []

    for group in producer_groups:
        session_group = {
            "producer": {
                "id": group["producer"]["id"],
                "name": group["producer"]["name"],
            },
            "producer_address": group["producer_address"],
            "min_delivery_date": str(group["min_delivery_date"]),  # Convert date to string
            "subtotal": group["subtotal"],
            "commission": group["commission"],
            "total": group["total"],
            "items": []
        }
        
        # Convert items to use IDs instead of objects
        for item in group["items"]:
            session_group["items"].append({
                "product_id": item["product"].product_id,
                "product_name": item["name"],
                "quantity": item["quantity"],
                "price": item["price"],
                "unit": item["unit"],
                "image": item["image"],
                "organic_certified": item["organic_certified"],
            })
        
        session_producer_groups.append(session_group)

    # Save the session-safe version
    request.session['producer_groups'] = session_producer_groups
    request.session['user_address'] = user_address
    request.session['overall_total'] = overall_total

        
    context = {
        "producer_groups": producer_groups,
        "total": overall_total,
        "user_address": user_address,
        "total_quantity": total_quantity,
        "summary_items": [],
    }
    
    print(f" Checkout prepared: {len(producer_groups)} producers, Total: £{overall_total}, Items: {total_quantity}")
    
    return render(request, "multi_checkout.html", context)


@login_required
def order_history(request):
    """Display all orders for the logged-in customer"""
    orders_list = Order.objects.filter(
        customer=request.user.customeraccount
    ).order_by('-created_at')
    
    # Add pagination (10 orders per page)
    paginator = Paginator(orders_list, 10)
    page_number = request.GET.get('page')
    orders = paginator.get_page(page_number)
    
    # Prepare order data with items
    order_data = []
    for order in orders:
        items = []
        for suborder in order.suborders.all():
            for item in suborder.items.all():
                items.append({
                    'name': item.product.name,
                    'quantity': item.quantity,
                    'price': item.price_at_purchase,
                    'producer': suborder.producer.business_name,
                    'delivery_date': suborder.delivery_date,
                    'status': suborder.status
                })
        
        order_data.append({
            'order_id': order.order_id,
            'date': order.created_at,
            'total': order.total_amount,
            'status': order.order_status,
            'item_count': len(items),
            'items': items[:3],  # Show first 3 items in preview
            'more_items': len(items) > 3
        })
    
    return render(request, 'order_history.html', {
        'orders': order_data,
        'page_obj': orders,
        'is_paginated': orders.has_other_pages()
    })


@login_required
def order_detail(request, order_id):
    """Display details for a specific order"""
    # Get the order or return 404
    order = get_object_or_404(
        Order, 
        order_id=order_id, 
        customer=request.user.customeraccount
    )
    
    # Group items by suborder/producer
    producers = []
    for suborder in order.suborders.all():
        items = []
        for item in suborder.items.all():
            items.append({
                'name': item.product.name,
                'quantity': item.quantity,
                'price': item.price_at_purchase,
                'image': item.product.image.url if item.product.image else None
            })
        
        producers.append({
            'name': suborder.producer.business_name,
            'delivery_date': suborder.delivery_date,
            'status': suborder.status,
            'items': items,
            'subtotal': suborder.subtotal,
            'payout': suborder.payout_amount
        })
    
    # Calculate commission (5% of total)
    commission = round(order.total_amount * 0.05, 2)
    
    return render(request, 'order_detail.html', {
        'order': order,
        'producers': producers,
        'total': order.total_amount,
        'commission': commission,
        'delivery_address': order.delivery_address,
        'delivery_postcode': order.delivery_postcode,
        'order_date': order.created_at,
        'status': order.order_status
    })