import stripe
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.utils import timezone
import json
from .models import PaymentTransaction, Commission
from order_management.models import Order, SubOrder, OrderItem
from shopping_cart.models import Cart
from user_accounts.models import ProducerAccount
from product.models import Product
from django.db import transaction
from notifications.utils import notify_producers_new_order  
from django.contrib import messages  

stripe.api_key = settings.STRIPE_SECRET_KEY

def create_payment_intent(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            intent = stripe.PaymentIntent.create(
                amount=int(float(data['total']) * 100),
                currency='gbp',
                payment_method_types=['card'],
                metadata={
                    'user_id': request.user.id,
                    'user_email': request.user.email
                }
            )
            return JsonResponse({'clientSecret': intent.client_secret})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def payment_page(request):
    if request.method == 'POST':
        total = request.POST.get('total')
        
        form_data = request.POST.dict()
        producer_data = {}
        for key, value in request.POST.items():
            if key.startswith('producer_') and (key.endswith('_delivery_date') or key.endswith('_method')):
                producer_data[key] = value
        
        request.session['checkout_data'] = {
            'total': total,
            'producer_data': producer_data,
            'form_data': form_data,
        }
        
        return render(request, 'payment.html', {
            'total': total,
            'stripe_public_key': settings.STRIPE_PUBLIC_KEY
        })
    return redirect('multi_checkout')

def payment_success(request):
    payment_intent_id = request.GET.get('payment_intent')
    
    if not payment_intent_id:
        return redirect('/')
    
    # ===== TRY TO FIND EXISTING ORDER FIRST =====
    try:
        # Try to find existing payment transaction
        existing_payment = PaymentTransaction.objects.get(stripe_payment_intent_id=payment_intent_id)
        order = existing_payment.order
        
        print(f" Found existing order #{order.order_id} for payment {payment_intent_id}")
        
        # Collect items from database
        all_items = []
        for suborder in order.suborders.all():
            for item in suborder.items.all():
                all_items.append({
                    'name': item.product.name,
                    'quantity': item.quantity,
                    'price': float(item.price_at_purchase),
                    'unit': item.product.unit if hasattr(item.product, 'unit') else '',
                    'image': item.product.image.url if item.product.image else None,
                    'producer': suborder.producer.business_name
                })
        
        # Check if any delivery was needed
        has_delivery = any(sub.delivery_date for sub in order.suborders.all())
        
        return render(request, 'payment_success.html', {
            'order_id': order.order_id,
            'total': float(order.total_amount),
            'items': all_items,
            'order_date': order.created_at,
            'customer_name': request.user.get_full_name() or request.user.email,
            'delivery_address': order.delivery_address if has_delivery else '',
            'delivery_postcode': order.delivery_postcode if has_delivery else '',
            'show_address': has_delivery,
            'user_email': request.user.email
        })
        
    except PaymentTransaction.DoesNotExist:
        # ===== NO EXISTING ORDER - CREATE NEW ONE =====
        print(f" No existing order found for {payment_intent_id}, creating new order")
        
        # Get checkout data from session
        checkout_data = request.session.get('checkout_data', {})
        user_address = request.session.get('user_address', {})
        producer_groups = request.session.get('producer_groups', [])
        
        if not producer_groups:
            return redirect('multi_checkout')
        
        # total = float(checkout_data.get('total', 0))
        # commission = round(total * 0.05, 2)

        total = sum(group['total'] for group in producer_groups)
        commission = sum(group['commission'] for group in producer_groups)


        
        # Check if any producer needs delivery
        has_delivery = False
        for group in producer_groups:
            producer_id = group['producer']['id']
            producer_data = checkout_data.get('producer_data', {})
            method_key = f'producer_{producer_id}_method'
            delivery_method = producer_data.get(method_key, 'delivery')
            if delivery_method == 'delivery':
                has_delivery = True
                break
        
        # Get the cart
        cart = Cart.objects.get(customer=request.user)
        
        # Create Order (only save address if needed)
        order = Order.objects.create(
            customer=request.user.customeraccount,
            total_amount=total,
            commission_amount=commission,
            delivery_address=user_address.get('street', '') if has_delivery else '',
            delivery_postcode=user_address.get('postcode', '') if has_delivery else '',
            order_status='Pending'
        )
        
        print(f" New order created: #{order.order_id}")
        
        # Create SubOrders and collect items
        all_items = []
        
        # Use transaction to ensure all stock updates happen together
        with transaction.atomic():
            for group in producer_groups:
                producer_id = group['producer']['id']
                producer_data = checkout_data.get('producer_data', {})
                date_key = f'producer_{producer_id}_delivery_date'
                delivery_date = producer_data.get(date_key, None)
                
                # producer = ProducerAccount.objects.get(id=producer_id)
                # subtotal = float(group['subtotal'])
                # producer_total = float(group['total'])
                
                # suborder = SubOrder.objects.create(
                #     order=order,
                #     producer=producer,
                #     delivery_date=delivery_date if delivery_date else None,
                #     subtotal=subtotal,
                #     payout_amount=producer_total,
                #     status='Pending',
                # )

                producer = ProducerAccount.objects.get(id=producer_id)

                subtotal = float(group['subtotal'])          
                commission = float(group['commission'])      
                producer_total = float(group['total'])       

                suborder = SubOrder.objects.create(
                    order=order,
                    producer=producer,
                    delivery_date=delivery_date if delivery_date else None,
                    subtotal=subtotal,            
                    payout_amount=subtotal,       
                    status='Pending',
                )

               
                for item_data in group['items']:
                    product = Product.objects.get(product_id=item_data['product_id'])
                    
                    quantity_purchased = item_data['quantity']
                    
                    # Check if enough stock exists (should be true, but double-check)
                    if product.stock_quantity >= quantity_purchased:
                        # Reduce the stock
                        product.stock_quantity -= quantity_purchased
                        
                        # Update availability status if stock becomes 0
                        if product.stock_quantity == 0:
                            product.availability_status = False
                        
                        product.save()
                        print(f" Stock reduced for {product.name}: +{quantity_purchased} purchased, {product.stock_quantity} remaining")
                    else:
                        # This shouldn't happen if cart validation worked, but handle just in case
                        print(f" ERROR: Not enough stock for {product.name}. Available: {product.stock_quantity}, Requested: {quantity_purchased}")
                        raise Exception(f"Insufficient stock for {product.name}")
                    
                    # Create order item
                    OrderItem.objects.create(
                        suborder=suborder,
                        product=product,
                        quantity=quantity_purchased,
                        price_at_purchase=item_data['price']
                    )
                    
                    all_items.append({
                        'name': item_data['product_name'],
                        'quantity': quantity_purchased,
                        'price': item_data['price'],
                        'unit': item_data.get('unit', ''),
                        'image': item_data.get('image', None),
                        'producer': producer.business_name
                    })
            
            # Create PaymentTransaction
            PaymentTransaction.objects.create(
                order=order,
                amount=total,
                currency='gbp',
                payment_method='card',
                payment_status='succeeded',
                stripe_payment_intent_id=payment_intent_id
            )
            
            # Create Commission
            Commission.objects.create(
                order=order,
                commission_amount=commission,
                producer_payout=total - commission,
                status='pending'
            )
        
        # Notify producers about the new order
        try:
            notify_producers_new_order(order)
            print(f"Sent new order notifications to producers for order #{order.order_id}")
        except Exception as e:
            print(f"Could not notify producers: {e}")
            
        
        # Clear cart and session
        cart.items.all().delete()
        session_keys = ['checkout_data', 'user_address', 'producer_groups']
        for key in session_keys:
            if key in request.session:
                del request.session[key]
        
        # Return success page
        return render(request, 'payment_success.html', {
            'order_id': order.order_id,
            'total': float(order.total_amount),
            'items': all_items,
            'order_date': order.created_at,
            'customer_name': request.user.get_full_name() or request.user.email,
            'delivery_address': order.delivery_address if has_delivery else '',
            'delivery_postcode': order.delivery_postcode if has_delivery else '',
            'show_address': has_delivery,
            'user_email': request.user.email
        })