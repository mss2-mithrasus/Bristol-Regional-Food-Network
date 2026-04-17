from django.contrib import messages

from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from datetime import timedelta
from user_accounts.models import CustomerAccount, Person, Address, ProducerAccount
from shopping_cart.models import Cart, CartItem
import logging
import random
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .models import Order, SubOrder, OrderItem
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
import json
import traceback
from django.db.models import Sum
from django.db import transaction
from producers.utils import is_product_valid_for_fulfilment, get_earliest_fulfilment_date
from producers.utils import expire_surplus_deals, deactivate_expired_products
from decimal import Decimal
from shopping_cart.models import get_bulk_discount_percentage

logger = logging.getLogger(__name__)

def order_home(request):
    return render(request, "base.html")


def multi_checkout(request):
    deactivate_expired_products()
    expire_surplus_deals()
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
        invalid_items = []
        for cart_item in cart.items.select_related('product').all():
            product = cart_item.product
            if not is_product_valid_for_fulfilment(product):
                invalid_items.append(cart_item)

        if invalid_items:
            for item in invalid_items:
                item.delete()

            messages.warning(
                request,
                "Some items were removed from your cart because they are no longer available for fulfilment."
            )
    except Cart.DoesNotExist:
        # No cart - empty checkout
        print(" No cart found")
        return render(request, 'multi_checkout.html', {
            'producer_groups': [],
            'total': 0,
            'user_address': None
        })
    
    # Get items grouped by producer using the model method (same as cart_view)
    cart.refresh_from_db()
    items_by_producer_dict = cart.get_items_grouped_by_producer()
    # felna added - Get account type for bulk discount
    try:
        account_type = user.customeraccount.account_type
    except Exception:
        account_type = "normal"
    print(f" Producers in cart: {len(items_by_producer_dict)}")
    
    # If producer names are "Unknown Producer", try to get them from items
    for producer, data in items_by_producer_dict.items():
        if data['producer_name'] == "Unknown Producer" and data['items']:
            # Get from the first item's producer_name property
            first_item = data['items'][0]
            if hasattr(first_item, 'producer_name'):
                data['producer_name'] = first_item.producer_name
                print(f"Fixed producer name: {data['producer_name']}")
    
    # Calculate 48-hour minimum delivery date
    min_delivery_date = (timezone.now() + timedelta(hours=48)).date()
    
    # Build producer_groups for template
    producer_groups = []
    overall_subtotal = 0
    total_quantity = 0  # Initialize total quantity counter
    
    for producer, data in items_by_producer_dict.items():
        # Customer pays this price (already includes commission)
        customer_price = float(data['subtotal'])

        # felna added - Apply bulk discount if applicable
        bulk_discount_pct = get_bulk_discount_percentage(
            account_type, Decimal(str(customer_price))
        )
        bulk_discount_amount = round(float(bulk_discount_pct) * customer_price / 100, 2)
        discounted_price = round(customer_price - bulk_discount_amount, 2)
        # change ended

        # Calculate commission (5% of customer price)
        producer_commission = round(customer_price * 0.05, 2)

        # Producer gets customer price minus commission
        producer_payout = customer_price - producer_commission

        # GET PRODUCER ADDRESS
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
        # END PRODUCER ADDRESS
        
        # Format items for template with MORE DETAILS
        formatted_items = []
        for item in data['items']:
            if not is_product_valid_for_fulfilment(item.product):
                continue
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
            
            # formatted_items.append({
            #     'product': product,
            #     'product_id': product.product_id if hasattr(product, 'product_id') else product.id,
            #     'name': product.name,
            #     'quantity': item.quantity,
            #     'price': float(product.price),
            #     'price_formatted': f"{float(product.price):.2f}",
            #     'unit': unit,
            #     'image': image_url,
            #     'organic_certified': organic,
            # })
            
            # Micaiah changed for surplus discount
            unit_price = float(item.unit_price)
            original_price = float(product.price)

            formatted_items.append({
                'product': product,
                'product_id': product.product_id if hasattr(product, 'product_id') else product.id,
                'name': product.name,
                'quantity': item.quantity,
                'price': unit_price,
                'price_formatted': f"{unit_price:.2f}",
                'unit': unit,
                'image': image_url,
                'organic_certified': organic,
                'original_price': original_price,
                'has_surplus_discount': unit_price != original_price,
            })
        if not formatted_items:
            continue
        
        producer_groups.append({
            "producer": {
                "id": data['producer_id'],
                "name": data['producer_name']
            },
            "producer_address": producer_address,
            "items": formatted_items,
            "min_delivery_date": min_delivery_date,
            "subtotal": customer_price,
            "subtotal_formatted": f"{customer_price:.2f}",
            "bulk_discount_pct": int(bulk_discount_pct),
            "bulk_discount_amount": bulk_discount_amount,
            "discounted_subtotal": discounted_price,
            "discounted_subtotal_formatted": f"{discounted_price:.2f}",
            "commission": producer_commission,
            "commission_formatted": f"{producer_commission:.2f}",
            "total": discounted_price,
            "total_formatted": f"{discounted_price:.2f}",
            "producer_payout": producer_payout,
        })

        overall_subtotal += discounted_price

    overall_total = sum(group['total'] for group in producer_groups)
    overall_total_formatted = f"{overall_total:.2f}"
    overall_subtotal_formatted = f"{overall_subtotal:.2f}"
    
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
            # OVERRIDE WITH SESSION IF EXISTS
            session_address = request.session.get('user_address')
            if session_address:
                user_address = session_address
                print(f"Using address from session: {user_address}")
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
            "min_delivery_date": str(group["min_delivery_date"]),
            "subtotal": group["subtotal"],
            "bulk_discount_pct": group["bulk_discount_pct"],
            "bulk_discount_amount": group["bulk_discount_amount"],
            "discounted_subtotal": group["discounted_subtotal"],
            "commission": group["commission"],
            "total": group["total"],
            "items": []
        }
        
        # Convert items to use IDs instead of objects
        for item in group["items"]:
            # session_group["items"].append({
            #     "product_id": item["product"].product_id,
            #     "product_name": item["name"],
            #     "quantity": item["quantity"],
            #     "price": item["price"],
            #     "unit": item["unit"],
            #     "image": item["image"],
            #     "organic_certified": item["organic_certified"],
            # })

            # Micaiah changed for surplus dicount 
            session_group["items"].append({
                "product_id": item["product"].product_id,
                "product_name": item["name"],
                "quantity": item["quantity"],
                "price": item["price"],  # discounted price if surplus is active
                "original_price": item.get("original_price"),
                "has_surplus_discount": item.get("has_surplus_discount", False),
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
        "total_formatted": f"{overall_total:.2f}",
        "user_address": user_address,
        "total_quantity": total_quantity,
        "summary_items": [],
        # felna added for bulk discount:
        "is_bulk_account": account_type in ["community", "restaurant"],
        "account_type": account_type,
    }
    
    print(f" Checkout prepared: {len(producer_groups)} producers, Total: £{overall_total}, Items: {total_quantity}")
    
    return render(request, "multi_checkout.html", context)

@login_required
def order_detail(request, order_id):
    """Display full details for a specific order"""
    try:
        order = Order.objects.get(
            order_id=order_id,
            customer=request.user.customeraccount
        )
    except Order.DoesNotExist:
        messages.error(request, "Order not found")
        return redirect('order_history')
    
    # Group by producer
    producers = []
    has_collection = False
    all_items = []  # For total_items count
    
    for suborder in order.suborders.all():
        items = []
        
        # Check if this is a collection order
        is_collection = not suborder.delivery_date
        
        for item in suborder.items.all():
            # Safer image URL handling (try/except instead of direct .url)
            image_url = None
            if hasattr(item.product, 'image') and item.product.image:
                try:
                    image_url = item.product.image.url
                except:
                    image_url = None
            original_price = getattr(item, "original_price_at_purchase", None) or item.price_at_purchase
            items.append({
                'name': item.product.name,
                'quantity': item.quantity,
                # 'price': item.price_at_purchase,
                # 'total': item.quantity * item.price_at_purchase,
                'price': float(item.price_at_purchase),
                'original_price': float(original_price),
                'has_surplus_discount': item.price_at_purchase != original_price,
                'total': float(item.quantity * item.price_at_purchase),
                'original_total': float(item.quantity * original_price),
                'image': image_url,
                'producer': suborder.producer.business_name,
                'product_id': item.product.product_id
            })

            # Track all items for total_items count
            all_items.append({
                'name': item.product.name,
                'quantity': item.quantity,
                'price': float(item.price_at_purchase)
            })
        
        # Get producer address for collection
        producer_address = None
        if is_collection and suborder.producer.address:
            producer_address = {
                'street': suborder.producer.address.address_line,
                'postcode': suborder.producer.address.postcode
            }
            has_collection = True
        
        status_history = []
        for history in suborder.status_history.all().order_by('-order_status_changed_at'):
            status_history.append({
                'old_status': history.old_status,
                'new_status': history.new_status,
                'changed_at': history.order_status_changed_at,
                'changed_by': history.stock_time_change.business_name if history.stock_time_change else 'System'
            })
        
        producers.append({
            'name': suborder.producer.business_name,
            'delivery_date': suborder.delivery_date,
            'status': suborder.status,
            'items': items,
            'subtotal': float(suborder.subtotal),
            'payout': float(suborder.payout_amount),
            'status_history': status_history,
            'is_collection': is_collection,
            'producer_address': producer_address,
            'special_instruction': suborder.special_instruction if hasattr(suborder, 'special_instruction') else None,  # Added from friend's version
        })
    # Determine overall status based on all suborders
    all_suborder_statuses = [suborder.status for suborder in order.suborders.all()]
    
    status_priority = {
    'Pending': 1,
    'Confirmed': 2,
    'Ready': 3,
    'Delivered': 4
}

    lowest_priority = 999
    overall_status = 'Delivered'

    for status in all_suborder_statuses:
        priority = status_priority.get(status, 0)
        if priority < lowest_priority:
            lowest_priority = priority
            overall_status = status
    
    # Special case: If all suborders are Delivered, show as Delivered
    all_delivered = all(status == 'Delivered' for status in all_suborder_statuses)
    if all_delivered:
        overall_status = 'Delivered'
    
    print(f" Order #{order.order_id} overall status: {overall_status} (suborder statuses: {all_suborder_statuses})")
    # Masked payment info
    masked_payment = {
        'card_last4': '4242',
        'card_type': 'VISA',
        'billing_address': order.delivery_address
    }
    
    # Calculate commission (5% of total)
    commission = float(order.commission_amount)

    # Total items count
    total_items = len(all_items)
    
    context = {
        'order': order,
        'order_number': f"ORD-{order.order_id:06d}",
        'producers': producers,
        'total': order.total_amount,
        'commission': commission,
        'delivery_address': order.delivery_address,
        'delivery_postcode': order.delivery_postcode,
        'order_date': order.created_at,
        'status': overall_status,
        'payment': masked_payment,
        'can_download': True,
        'has_collection': has_collection,
        'total_items': total_items,  # Added from friend's version
    }
    
    return render(request, 'order_detail.html', context)

@login_required
def order_history(request):
    """Display all orders for the logged-in customer"""
    try:
        customer = request.user.customeraccount
    except:
        messages.error(request, "Customer account not found")
        return redirect('home')

    orders_list = Order.objects.filter(
        customer=customer
    ).order_by('-created_at')

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    producer_filter = request.GET.get('producer')

    if date_from:
        orders_list = orders_list.filter(created_at__date__gte=date_from)
    if date_to:
        orders_list = orders_list.filter(created_at__date__lte=date_to)

    all_producers = set()
    for order in orders_list:
        for suborder in order.suborders.all():
            all_producers.add(suborder.producer.business_name)

    if producer_filter and producer_filter != 'all':
        orders_list = orders_list.filter(
            suborders__producer__business_name=producer_filter
        ).distinct()

    paginator = Paginator(orders_list, 5)
    page_number = request.GET.get('page')
    orders = paginator.get_page(page_number)

    order_data = []
    for order in orders:
        preview_items = []
        producers_data = []
        special_instructions = []

        confirmed_count = 0
        ready_count = 0
        delivered_count = 0
        collected_count = 0
        total_producers = order.suborders.count()

        for suborder in order.suborders.all():
            is_delivery = suborder.delivery_date is not None
            display_status = suborder.status

            # Correctly distinguish delivered vs collected
            if suborder.status == "Delivered":
                if is_delivery:
                    display_status = "Delivered"
                    delivered_count += 1
                else:
                    display_status = "Collected"
                    collected_count += 1

            # Count confirmed producers (those at Confirmed, Ready, or Delivered stage)
            if suborder.status in ["Confirmed", "Ready", "Delivered"]:
                confirmed_count += 1

            # Count ready producers (those at Ready or Delivered stage)
            if suborder.status in ["Ready", "Delivered"]:
                ready_count += 1

            producer_info = {
                'name': suborder.producer.business_name,
                'delivery_date': suborder.delivery_date,
                'status': suborder.status,
                'display_status': display_status,
                'is_delivery': is_delivery,
                'delivery_date': suborder.delivery_date,
                'item_count': suborder.items.count(),
                'subtotal': float(suborder.subtotal),
            }

            producers_data.append(producer_info)

            # Collect special instructions
            if suborder.special_instruction:
                special_instructions.append({
                    'producer': suborder.producer.business_name,
                    'instruction': suborder.special_instruction
                })

            # Preview items (first 2 per producer)
            # for item in suborder.items.all()[:2]:
            #     preview_items.append({
            #         'name': item.product.name,
            #         'quantity': item.quantity,
            #         'price': item.price_at_purchase,
            #         'producer': suborder.producer.business_name
            #     })
             
            # Micaiah added for surplus discount
            for item in suborder.items.all()[:2]:
                # original_price = item.original_price_at_purchase or item.price_at_purchase
                original_price = getattr(item, "original_price_at_purchase", None) or item.price_at_purchase
                preview_items.append({
                    'name': item.product.name,
                    'quantity': item.quantity,
                    'price': float(item.price_at_purchase),
                    'original_price': float(original_price),
                    'has_surplus_discount': item.price_at_purchase != original_price,
                    'producer': suborder.producer.business_name
                })

        total_items = sum(p['item_count'] for p in producers_data)

        # Overall status logic
        all_statuses = [p['status'] for p in producers_data]

        # Map status priority: Delivered (or Collected) is highest, then Ready, then Confirmed, then Pending
        status_priority = {
        'Pending': 1,
        'Confirmed': 2,
        'Ready': 3,
        'Delivered': 4
        }

        lowest_priority = 999
        overall_status = 'Delivered'

        for status in all_statuses:
            priority = status_priority.get(status, 0)
            if priority < lowest_priority:
                lowest_priority = priority
                overall_status = status

        # Special case: If all producers are either Delivered or Collected, show as Delivered
        all_delivered_or_collected = all(
            p['status'] == 'Delivered' for p in producers_data
        )
        if all_delivered_or_collected:
            overall_status = 'Delivered'
        order_data.append({
            'order_id': order.order_id,
            'order_number': f"ORD-{order.order_id:06d}",
            'date': order.created_at,
            'status': overall_status,
            'total': order.total_amount,
            'item_count': total_items,
            'items': preview_items[:3],
            'more_items': len(preview_items) > 3,
            'preview_items': preview_items[:4],
            'friend_more_items': len(preview_items) > 4,
            'producers': producers_data,
            'total_producers': total_producers,
            'confirmed_count': confirmed_count,
            'ready_count': ready_count,
            'delivered_count': delivered_count,
            'collected_count': collected_count,
            'special_instructions': special_instructions,
        })

    context = {
        'orders': order_data,
        'page_obj': orders,
        'is_paginated': orders.has_other_pages(),
        'producer_filters': sorted(list(all_producers)),
        'date_from': date_from,
        'date_to': date_to,
        'selected_producer': producer_filter if producer_filter else 'all',
    }

    return render(request, 'order_history.html', context)


@login_required
def reorder(request, order_id):
    """Reorder all items from a previous order"""
    print(f" REORDER FUNCTION CALLED for order {order_id}")
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        order = Order.objects.get(
            order_id=order_id,
            customer=request.user.customeraccount
        )
        print(f" Order found: {order}")
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    
    with transaction.atomic():
        cart, created = Cart.objects.get_or_create(customer=request.user)
        print(f" Cart {'created' if created else 'found'}")
        
        now = timezone.now()
        expired = cart.items.filter(reserved_until__lt=now)
        if expired.exists():
            print(f" Cleaning {expired.count()} expired items")
            expired.delete()
        
        unavailable_items = []
        added_items = []
        total_amount = 0
        total_items = 0
        
        for suborder in order.suborders.all():
            for order_item in suborder.items.all():
                product = order_item.product
                quantity = order_item.quantity
                price = float(order_item.price_at_purchase)
                item_total = price * quantity
                
                print(f"  - Processing: {product.name}, Qty: {quantity}")
                
                try:
                    # Check if product exists and is active
                    if not product or not hasattr(product, 'availability_status') or not product.availability_status:
                        unavailable_items.append({
                            'name': order_item.product.name,
                            'quantity': quantity,
                            'price': price,
                            'total': item_total,
                            'producer': suborder.producer.business_name,
                            'reason': 'Product no longer available'
                        })
                        continue
                    
                    # Get ALL active reservations from OTHER users
                    other_users_reservations = CartItem.objects.filter(
                        product=product,
                        reserved_until__gt=timezone.now()
                    ).exclude(
                        cart__customer=request.user
                    ).aggregate(total=Sum('quantity'))['total'] or 0
                    
                    user_cart_item = CartItem.objects.filter(
                        cart=cart,
                        product=product
                    ).first()
                    
                    user_current_quantity = user_cart_item.quantity if user_cart_item else 0
                    
                    if hasattr(product, 'stock_quantity'):
                        available_to_add = product.stock_quantity - other_users_reservations - user_current_quantity
                    else:
                        available_to_add = 999999
                    
                    if hasattr(product, 'stock_quantity') and quantity > available_to_add:
                        unavailable_items.append({
                            'name': product.name,
                            'quantity': quantity,
                            'price': price,
                            'total': item_total,
                            'producer': suborder.producer.business_name,
                            'available': available_to_add,
                            'reason': f'Only {available_to_add} available'
                        })
                        continue
                    
                    reservation_expiry = timezone.now() + timedelta(minutes=30)
                    
                    if user_cart_item:
                        user_cart_item.quantity += quantity
                        user_cart_item.reserved_until = reservation_expiry
                        user_cart_item.save()
                    else:
                        CartItem.objects.create(
                            cart=cart,
                            product=product,
                            quantity=quantity,
                            reserved_until=reservation_expiry
                        )
                    
                    added_items.append({
                        'name': product.name,
                        'quantity': quantity,
                        'price': price,
                        'total': item_total,
                        'producer': suborder.producer.business_name
                    })
                    
                    total_amount += item_total
                    total_items += quantity
                    
                except Exception as e:
                    print(f"     Error: {e}")
                    traceback.print_exc()
                    unavailable_items.append({
                        'name': order_item.product.name,
                        'quantity': quantity,
                        'price': price,
                        'total': item_total,
                        'producer': suborder.producer.business_name,
                        'error': str(e)
                    })
        
        response_data = {
            'success': True,
            'added_count': len(added_items),
            'added_items': added_items,
            'unavailable_count': len(unavailable_items),
            'unavailable_items': unavailable_items,
            'total_amount': total_amount,
            'total_amount_formatted': f"£{total_amount:.2f}",
            'total_items': total_items,
        }
        
        if unavailable_items:
            unavailable_total = sum(item['total'] for item in unavailable_items)
            response_data['unavailable_total'] = unavailable_total
            response_data['unavailable_total_formatted'] = f"£{unavailable_total:.2f}"
        
        return JsonResponse(response_data)
    
"""@login_required
def download_receipt(request, order_id):
    #View receipt (printable version)
    try:
        order = Order.objects.get(
            order_id=order_id,
            customer=request.user.customeraccount
        )
    except Order.DoesNotExist:
        messages.error(request, "Order not found")
        return redirect('order_history')
    
    # Collect items (similar to payment_success)
    items = []
    for suborder in order.suborders.all():
        for item in suborder.items.all():
            items.append({
                'name': item.product.name,
                'quantity': item.quantity,
                'price': item.price_at_purchase,
                'unit': item.product.unit if hasattr(item.product, 'unit') else '',
                'image': item.product.image.url if item.product.image else None,
                'producer': suborder.producer.business_name
            })
    
    context = {
        'order_id': order.order_id,
        'total': order.total_amount,
        'items': items,
        'order_date': order.created_at,
        'customer_name': request.user.get_full_name() or request.user.email,
        'delivery_address': order.delivery_address,
        'delivery_postcode': order.delivery_postcode,
        'is_receipt_view': True,  # Flag to hide success message
    }
    
    return render(request, 'payment_success.html', context)"""

def update_checkout_address(request):
    """Save edited address to session"""
    print("=" * 50)
    print("update_checkout_address view called")
    print(f"Request method: {request.method}")
    print(f"User authenticated: {request.user.is_authenticated}")
    
    if request.method == 'POST':
        try:
            print(f"Request body: {request.body}")
            
            # Try to parse JSON
            try:
                data = json.loads(request.body)
                print(f"Parsed data: {data}")
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                return JsonResponse({'success': False, 'error': f'Invalid JSON: {str(e)}'}, status=400)
            
            # Validate data
            street = data.get('street')
            postcode = data.get('postcode')
            
            if street is None or postcode is None:
                return JsonResponse({'success': False, 'error': 'Missing street or postcode'}, status=400)
            
            # Save to session
            print(f"Saving to session: street={street}, postcode={postcode}")
            
            # Making sure session is working
            request.session['checkout_address'] = {
                'street': street,
                'postcode': postcode,
            }
            
            request.session['user_address'] = {
                'street': street,
                'postcode': postcode,
            }
            
            # Force session save
            request.session.modified = True
            
            print(f"Session saved: {request.session.get('user_address')}")
            print("=" * 50)
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            print(f"UNEXPECTED ERROR: {e}")
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    print("Method not allowed")
    print("=" * 50)
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405) #need to use this 