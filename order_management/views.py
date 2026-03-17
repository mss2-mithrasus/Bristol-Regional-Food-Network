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
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
import json
import traceback
import requests
from django.conf import settings


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
        print(" User not authenticated, redirecting to login")
        return redirect('login')
    
    # Get cart for this user
    try:
        cart = Cart.objects.get(customer=user)
        print(f" Cart found: {cart.cart_id}, Items: {cart.total_items}")
    except Cart.DoesNotExist:
        print(" No cart found")
        return render(request, 'multi_checkout.html', {
            'producer_groups': [],
            'total': '0.00',
            'user_address': None
        })
    
    # Get items grouped by producer
    items_by_producer_dict = cart.get_items_grouped_by_producer()
    print(f" Producers in cart: {len(items_by_producer_dict)}")
    
    # Fix producer names if needed
    for producer, data in items_by_producer_dict.items():
        if data['producer_name'] == "Unknown Producer" and data['items']:
            first_item = data['items'][0]
            if hasattr(first_item, 'producer_name'):
                data['producer_name'] = first_item.producer_name
                print(f"Fixed producer name: {data['producer_name']}")
    
    # Calculate 48‑hour minimum delivery date
    min_delivery_date = (timezone.now() + timedelta(hours=48)).date()
    
    # Build producer_groups for template
    producer_groups = []
    overall_subtotal = 0
    total_quantity = 0
    
    for producer, data in items_by_producer_dict.items():
        producer_subtotal = float(data['subtotal'])
        producer_commission = round(producer_subtotal * 0.05, 2)
        producer_total = round(producer_subtotal * 1.05, 2)
        
        # Get producer address
        producer_address = None
        try:
            if hasattr(producer, 'produceraccount'):
                producer_account = producer.produceraccount
            elif hasattr(producer, 'address'):
                producer_account = producer
            else:
                producer_account = ProducerAccount.objects.get(user=producer)
            
            if producer_account and hasattr(producer_account, 'address') and producer_account.address:
                producer_address = {
                    'street': producer_account.address.address_line,
                    'postcode': producer_account.address.postcode,
                }
        except Exception as e:
            print(f"Error getting producer address: {e}")
            producer_address = None
        
        # Format items for template
        formatted_items = []
        for item in data['items']:
            product = item.product
            total_quantity += item.quantity
            
            image_url = None
            if hasattr(product, 'image') and product.image:
                try:
                    image_url = product.image.url
                except:
                    image_url = None
            
            unit = ''
            if hasattr(product, 'unit') and product.unit:
                unit = product.unit
            
            organic = False
            if hasattr(product, 'organic_certified'):
                organic = product.organic_certified
            
            formatted_items.append({
                'product': product,
                'product_id': product.product_id if hasattr(product, 'product_id') else product.id,
                'name': product.name,
                'quantity': item.quantity,
                'price': float(product.price),
                'price_formatted': "{:.2f}".format(float(product.price)),  # Formatted price
                'unit': unit,
                'image': image_url,
                'organic_certified': organic,
            })
        
        producer_groups.append({
            "producer": {
                "id": data['producer_id'],
                "name": data['producer_name']
            },
            "producer_address": producer_address,
            "items": formatted_items,
            "min_delivery_date": min_delivery_date,
            "subtotal": producer_subtotal,
            "subtotal_formatted": "{:.2f}".format(producer_subtotal),  # Formatted subtotal
            "commission": producer_commission,
            "commission_formatted": "{:.2f}".format(producer_commission),  # Formatted commission
            "total": producer_total,
            "total_formatted": "{:.2f}".format(producer_total),  # Formatted total
        })
        
        overall_subtotal += producer_subtotal
    
    overall_total = round(overall_subtotal * 1.05, 2)
    overall_total_formatted = "{:.2f}".format(overall_total)
    overall_subtotal_formatted = "{:.2f}".format(overall_subtotal)
    
    # ===== GET USER ADDRESS - PRIORITIZE SESSION, THEN DATABASE =====
    user_address = None
    if user.is_authenticated:
        # First check session (from update_checkout_address)
        session_address = request.session.get('user_address')
        if session_address:
            user_address = session_address
            print(f"Using address from session: {user_address}")
        else:
            # Fall back to database
            try:
                customer = CustomerAccount.objects.get(user=user)
                if customer.address:
                    user_address = {
                        'street': customer.address.address_line,
                        'postcode': customer.address.postcode,
                    }
                    print(f"Using address from database: {user_address}")
                else:
                    user_address = {
                        'street': 'No address saved',
                        'postcode': '',
                    }
            except CustomerAccount.DoesNotExist:
                user_address = {
                    'street': 'Please create a customer profile',
                    'postcode': '',
                }
    
    # Save to session for consistency
    if user_address:
        request.session['user_address'] = user_address
    
    # Create session-safe copy of producer groups
    session_producer_groups = []
    for group in producer_groups:
        session_group = {
            "producer": {
                "id": group["producer"]["id"],
                "name": group["producer"]["name"],
            },
            "producer_address": group["producer_address"],
            "min_delivery_date": str(group["min_delivery_date"]),
            "subtotal": group["subtotal"],
            "subtotal_formatted": group["subtotal_formatted"],
            "commission": group["commission"],
            "commission_formatted": group["commission_formatted"],
            "total": group["total"],
            "total_formatted": group["total_formatted"],
            "items": []
        }
        
        for item in group["items"]:
            session_group["items"].append({
                "product_id": item["product"].product_id,
                "product_name": item["name"],
                "quantity": item["quantity"],
                "price": item["price"],
                "price_formatted": item["price_formatted"],
                "unit": item["unit"],
                "image": item["image"],
                "organic_certified": item["organic_certified"],
            })
        
        session_producer_groups.append(session_group)
    
    request.session['producer_groups'] = session_producer_groups
    request.session['overall_total'] = overall_total
    request.session['overall_total_formatted'] = overall_total_formatted
    
    context = {
        "producer_groups": producer_groups,
        "total": overall_total,
        "total_formatted": overall_total_formatted,
        "subtotal_formatted": overall_subtotal_formatted,
        "user_address": user_address,
        "total_quantity": total_quantity,
        "summary_items": [],
    }
    
    print(f" Checkout prepared: {len(producer_groups)} producers, Total: £{overall_total_formatted}")
    
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



def update_checkout_address(request):
    """Save edited address to session (NO validation)"""
    print("=" * 50)
    print("update_checkout_address view called")
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print(f"Received data: {data}")
            
            street = data.get('street')
            postcode = data.get('postcode')
            
            if street is None or postcode is None:
                return JsonResponse({'success': False, 'error': 'Missing street or postcode'}, status=400)
            
            # Clean postcode
            postcode = postcode.strip().upper()
            
            # NO VALIDATION HERE - just save to session
            request.session['checkout_address'] = {
                'street': street,
                'postcode': postcode,
            }
            
            request.session['user_address'] = {
                'street': street,
                'postcode': postcode,
            }
            
            request.session.modified = True
            
            print(f"Address saved to session: {street}, {postcode}")
            
            return JsonResponse({
                'success': True,
                'message': 'Address saved successfully'
            })
            
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

def lookup_postcode(request):
    """Get all addresses for a UK postcode using GetAddress.io"""
    postcode = request.GET.get('postcode', '').strip().upper()
    
    if not postcode:
        return JsonResponse({'error': 'Postcode required'}, status=400)
    
    # Get your GetAddress.io API key from settings
    api_key = settings.GETADDRESS_API_KEY  # Add this to your settings.py
    
    try:
        # Call GetAddress.io API
        response = requests.get(
            f'https://api.getaddress.io/find/{postcode}',
            params={'api-key': api_key},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            
            addresses = []
            for addr in data.get('addresses', []):
                # Format the address components
                addresses.append({
                    'full_address': addr['address'],
                    'line_1': addr.get('line_1', ''),
                    'line_2': addr.get('line_2', ''),
                    'line_3': addr.get('line_3', ''),
                    'city': addr.get('town_or_city', ''),
                    'postcode': postcode
                })
            
            return JsonResponse({
                'success': True,
                'addresses': addresses,
                'count': len(addresses)
            })
            
        elif response.status_code == 404:
            return JsonResponse({
                'success': False,
                'error': 'Postcode not found'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'API error: {response.status_code}'
            })
            
    except requests.ConnectionError:
        return JsonResponse({
            'success': False,
            'error': 'Cannot connect to address service'
        })
    except requests.Timeout:
        return JsonResponse({
            'success': False,
            'error': 'Address service timeout'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })