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
        total = request.POST.get('total') or "0"

        # Extract producer-specific fields
        form_data = request.POST.dict()
        producer_data = {}

        for key, value in request.POST.items():
            if key.startswith('producer_') and (
                key.endswith('_delivery_date') or 
                key.endswith('_method') or 
                key.endswith('_special_instruction')
            ):
                producer_data[key] = value

        # Store everything in session
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

    # Try to find an existing order first
    try:
        existing_payment = PaymentTransaction.objects.get(
            stripe_payment_intent_id=payment_intent_id
        )
        order = existing_payment.order

        # Collect items for display
        all_items = []
        for suborder in order.suborders.all():
            for item in suborder.items.all():
                all_items.append({
                    'name': item.product.name,
                    'quantity': item.quantity,
                    'price': float(item.price_at_purchase),
                    'unit': getattr(item.product, 'unit', ''),
                    'image': item.product.image.url if item.product.image else None,
                    'producer': suborder.producer.business_name
                })

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
        # No existing order — create a new one
        checkout_data = request.session.get('checkout_data', {})
        user_address = request.session.get('user_address', {})
        producer_groups = request.session.get('producer_groups', [])

        if not producer_groups:
            return redirect('multi_checkout')

        # SAFE float conversion
        total = sum(float(group.get('total') or 0) for group in producer_groups)
        commission = sum(float(group.get('commission') or 0) for group in producer_groups)

        # Determine if any producer requires delivery
        has_delivery = False
        producer_data = checkout_data.get('producer_data', {})

        for group in producer_groups:
            pid = group['producer']['id']
            method = producer_data.get(f'producer_{pid}_method', 'delivery')
            if method == 'delivery':
                has_delivery = True
                break

        # Create main order
        cart = Cart.objects.get(customer=request.user)

        order = Order.objects.create(
            customer=request.user.customeraccount,
            total_amount=total,
            commission_amount=commission,
            delivery_address=user_address.get('street', '') if has_delivery else '',
            delivery_postcode=user_address.get('postcode', '') if has_delivery else '',
            order_status='Pending'
        )

        all_items = []

        # Create suborders + update stock
        with transaction.atomic():
            for group in producer_groups:
                pid = group['producer']['id']
                producer = ProducerAccount.objects.get(id=pid)

                # Delivery date
                delivery_date = producer_data.get(f'producer_{pid}_delivery_date') or None

                # Special instruction
                special_instruction = producer_data.get(
                    f'producer_{pid}_special_instruction', ''
                )

                # SAFE float conversions
                customer_pays = float(group.get('subtotal') or 0)
                commission_amount = float(group.get('commission') or 0)
                producer_gets = customer_pays - commission_amount

                suborder = SubOrder.objects.create(
                    order=order,
                    producer=producer,
                    delivery_date=delivery_date,
                    subtotal=customer_pays,
                    payout_amount=producer_gets,
                    status='Pending',
                    special_instruction=special_instruction,
                )

                # Create order items + update stock
                for item_data in group['items']:
                    product = Product.objects.get(product_id=item_data['product_id'])
                    qty = item_data['quantity']

                    if product.stock_quantity < qty:
                        raise Exception(f"Insufficient stock for {product.name}")

                    product.stock_quantity -= qty
                    if product.stock_quantity == 0:
                        product.availability_status = False
                    product.save()

                    OrderItem.objects.create(
                        suborder=suborder,
                        product=product,
                        quantity=qty,
                        price_at_purchase=item_data['price']
                    )

                    all_items.append({
                        'name': item_data['product_name'],
                        'quantity': qty,
                        'price': item_data['price'],
                        'unit': item_data.get('unit', ''),
                        'image': item_data.get('image', None),
                        'producer': producer.business_name
                    })

            # Create payment transaction
            PaymentTransaction.objects.create(
                order=order,
                amount=total,
                currency='gbp',
                payment_method='card',
                payment_status='succeeded',
                stripe_payment_intent_id=payment_intent_id
            )

            # Create commission record
            Commission.objects.create(
                order=order,
                commission_amount=commission,
                producer_payout=total - commission,
                status='pending'
            )

        # Notify producers
        try:
            notify_producers_new_order(order)
        except Exception as e:
            print("Notification error:", e)

        # Clear cart + session
        cart.items.all().delete()
        for key in ['checkout_data', 'user_address', 'producer_groups']:
            request.session.pop(key, None)

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