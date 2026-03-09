from django.shortcuts import render, redirect
from django.utils import timezone
from datetime import timedelta
from user_accounts.models import CustomerAccount, Person, Address, ProducerAccount
from shopping_cart.models import Cart
import logging
import random

logger = logging.getLogger(__name__)

def order_home(request):
    return render(request, "base.html")

def payment(request):
    return render(request, "payment.html")

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
            "items": formatted_items,
            "min_delivery_date": min_delivery_date,
            "subtotal": producer_subtotal,
            "commission": producer_commission,
            "total": producer_total,
        })
        
        overall_subtotal += producer_subtotal
    
    overall_total = round(overall_subtotal * 1.05, 2)
    
    # Get user address - FIXED to match your Address model
    user_address = None
    if user.is_authenticated:
        try:
            customer = CustomerAccount.objects.get(user=user)
            
            # Get person name
            if customer.person:
                full_name = f"{customer.person.first_name} {customer.person.last_name}"
                phone = customer.person.phone or ""
            else:
                full_name = user.email
                phone = ""
            
            # Get address - only fields that exist
            if customer.address:
                street = customer.address.address_line
                postcode = customer.address.postcode
            else:
                street = "No address saved"
                postcode = ""
            
            user_address = {
                'full_name': full_name,
                'email': user.email,
                'phone': phone,
                'street': street,
                'postcode': postcode,
            }
        except CustomerAccount.DoesNotExist:
            user_address = {
                'full_name': user.email,
                'email': user.email,
                'phone': '',
                'street': 'Please create a customer profile',
                'postcode': '',
            }
    
    context = {
        "producer_groups": producer_groups,
        "total": overall_total,
        "user_address": user_address,
        "total_quantity": total_quantity,  # ADD THIS LINE
        "summary_items": [],
    }
    
    print(f" Checkout prepared: {len(producer_groups)} producers, Total: £{overall_total}, Items: {total_quantity}")
    
    return render(request, "multi_checkout.html", context)