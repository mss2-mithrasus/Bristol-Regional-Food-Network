import stripe
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.utils import timezone
import json
from .models import PaymentTransaction, Commission
from order_management.models import Order, SubOrder, OrderItem, RecurringTemplate, RecurringOrderInstance
from shopping_cart.models import Cart
from user_accounts.models import ProducerAccount
from product.models import Product
from django.db import transaction
from notifications.utils import notify_producers_new_order  
from django.contrib import messages
from decimal import Decimal, ROUND_HALF_UP
from producers.utils import (
    deactivate_surplus_if_sold_out,
    is_product_valid_for_fulfilment,
    deactivate_expired_products,
    expire_surplus_deals,
)
stripe.api_key = settings.STRIPE_SECRET_KEY
#felna added 
def get_display_name(user):
    try:
        acc = user.customeraccount
        if acc.account_type == "community":
            return acc.communitygroup.organisation_name
        elif acc.account_type == "restaurant":
            return acc.restaurant.organisation_name
        elif acc.person:
            return f"{acc.person.first_name} {acc.person.last_name}"
    except Exception:
        pass
    return user.email
#change ended
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
    
    deactivate_expired_products()
    expire_surplus_deals()

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
                original_price = getattr(item, "original_price_at_purchase", None) or item.price_at_purchase
                all_items.append({
                    'name': item.product.name,
                    'quantity': item.quantity,
                    'price': float(item.price_at_purchase),
                    'original_price': float(original_price),
                    'has_surplus_discount': item.price_at_purchase != original_price,
                    'unit': getattr(item.product, 'unit', ''),
                    'image': item.product.image.url if item.product.image else None,
                    'producer': suborder.producer.business_name,
                    'producer_email': suborder.producer.user.email,
                    'producer_phone': suborder.producer.contact_person.phone if suborder.producer.contact_person else '',
                })

        
        has_delivery = any(sub.fulfillment_method == 'delivery' for sub in order.suborders.all())
        
        return render(request, 'payment_success.html', {
            'order_id': order.order_id,
            'total': float(order.total_amount),
            'items': all_items,
            'order_date': order.created_at,
            'customer_name': get_display_name(request.user),
            'delivery_address': order.delivery_address if has_delivery else '',
            'delivery_postcode': order.delivery_postcode if has_delivery else '',
            'show_address': has_delivery,
            'user_email': request.user.email
        })

    except PaymentTransaction.DoesNotExist:
        checkout_data = request.session.get('checkout_data', {})
        user_address = request.session.get('user_address', {})
        producer_groups = request.session.get('producer_groups', [])

        if not producer_groups:
            return redirect('multi_checkout')

        invalid_products = []
        for group in producer_groups:
            for item_data in group['items']:
                try:
                    product = Product.objects.get(product_id=item_data['product_id'])
                except Product.DoesNotExist:
                    invalid_products.append(item_data.get('product_name', 'Unknown product'))
                    continue

               
                if not product.availability_status or not is_product_valid_for_fulfilment(product):
                    if product.name not in invalid_products:
                        invalid_products.append(product.name)
        if invalid_products:
            messages.error(
                request,
                "Some items in your order are no longer available for fulfilment: "
                + ", ".join(invalid_products)
            )
            return redirect('multi_checkout')

        total = sum(float(group.get('total') or 0) for group in producer_groups)
        commission = sum(float(group.get('commission') or 0) for group in producer_groups)

        has_delivery = False
        producer_data = checkout_data.get('producer_data', {})

        for group in producer_groups:
            pid = group['producer']['id']
            method = producer_data.get(f'producer_{pid}_method', 'delivery')
            if method == 'delivery':
                has_delivery = True
                break

        try:
            cart = Cart.objects.get(customer=request.user)
            all_items = []

            with transaction.atomic():
                order = Order.objects.create(
                    customer=request.user.customeraccount,
                    total_amount=total,
                    commission_amount=commission,
                    delivery_address=user_address.get('street', '') if has_delivery else '',
                    delivery_postcode=user_address.get('postcode', '') if has_delivery else '',
                    order_status='Pending'
                )

                for group in producer_groups:
                    pid = group['producer']['id']
                    producer = ProducerAccount.objects.get(id=pid)

                    raw_method = producer_data.get(f'producer_{pid}_method', 'delivery')
                    fulfillment_method = 'collection' if raw_method in ['collect', 'collection'] else 'delivery'

                    delivery_date = producer_data.get(f'producer_{pid}_delivery_date') or None
                    if not delivery_date:
                        raise Exception(
                            f"Please select a {'collection' if fulfillment_method == 'collection' else 'delivery'} date for {producer.business_name}."
                        )
                    special_instruction = producer_data.get(
                        f'producer_{pid}_special_instruction', ''
                    )
                    
                    customer_pays = Decimal(str(group.get('discounted_subtotal') or group.get('subtotal') or "0"))

                    commission_amount = (customer_pays * Decimal("0.05")).quantize(
                        Decimal("0.01"),
                        rounding=ROUND_HALF_UP
                    )

                    producer_gets = (customer_pays * Decimal("0.95")).quantize(
                        Decimal("0.01"),
                        rounding=ROUND_HALF_UP
                    )

                    suborder = SubOrder.objects.create(
                        order=order,
                        producer=producer,
                        delivery_date=delivery_date,
                        fulfillment_method=fulfillment_method,
                        subtotal=customer_pays,
                        payout_amount=producer_gets,
                        status='Pending',
                        special_instruction=special_instruction,
                    )

                    for item_data in group['items']:
                        product = Product.objects.select_for_update().get(
                            product_id=item_data['product_id']
                        )
                        qty = item_data['quantity']

                        if not product.availability_status:
                            raise Exception(f"{product.name} is no longer available.")

                        if not is_product_valid_for_fulfilment(product):
                            raise Exception(f"{product.name} is no longer available for fulfilment.")
                        
                        if product.stock_quantity < qty:
                            raise Exception(f"Insufficient stock for {product.name}")

                        product.stock_quantity -= qty
                        if product.stock_quantity == 0:
                            product.availability_status = False
                        product.save()

                        from producers.low_stock_service import check_low_stock
                        check_low_stock(product)
                        deactivate_surplus_if_sold_out(product)

                        price_at_purchase = item_data['price']
                        original_price_at_purchase = item_data.get('original_price') or item_data['price']

                        OrderItem.objects.create(
                            suborder=suborder,
                            product=product,
                            quantity=qty,
                            price_at_purchase=price_at_purchase,
                            original_price_at_purchase=original_price_at_purchase
                        )

                        all_items.append({
                            'name': item_data['product_name'],
                            'quantity': qty,
                            'price': float(price_at_purchase),
                            'original_price': float(original_price_at_purchase),
                            'has_surplus_discount': float(price_at_purchase) != float(original_price_at_purchase),
                            'unit': item_data.get('unit', ''),
                            'image': item_data.get('image', None),
                            'producer': producer.business_name,
                            'producer_email': producer.user.email,
                            'producer_phone': producer.contact_person.phone if producer.contact_person else '',
                        
                        })

                PaymentTransaction.objects.create(
                    order=order,
                    amount=total,
                    currency='gbp',
                    payment_method='card',
                    payment_status='succeeded',
                    stripe_payment_intent_id=payment_intent_id
                )

                Commission.objects.create(
                    order=order,
                    commission_amount=commission,
                    producer_payout=total - commission,
                    status='pending'
                )

        except Exception as e:
            messages.error(request, str(e))
            return redirect('multi_checkout')

        try:
            notify_producers_new_order(order)
        except Exception as e:
            print("Notification error:", e)


        # RECURRING ORDER TEMPLATE (Restaurant only)
        form_data = checkout_data.get('form_data', {})
        is_recurring = form_data.get('recurring') == 'true'
        if is_recurring and request.user.customeraccount.account_type == 'restaurant':
            recurrence = form_data.get('recurrence')
            delivery_weekday = int(form_data.get('delivery_weekday', 0))
            start_date = form_data.get('start_date')
            end_date = form_data.get('end_date') or None

            # Get the custom name from the form input
            recurring_name = form_data.get('recurring_name', '').strip()
            if not recurring_name:
                recurring_name = f"Recurring order from {timezone.now().date()}"

            # Build items list from the order we just created
            items_list = []
            for suborder in order.suborders.all():
                for item in suborder.items.all():
                    items_list.append({
                        'product_id': item.product.product_id,
                        'quantity': item.quantity
                    })

            # Create the template
            RecurringTemplate.objects.create(
                customer=request.user.customeraccount,
                name=recurring_name,    
                recurrence=recurrence,
                delivery_weekday=delivery_weekday,
                start_date=start_date,
                end_date=end_date,
                is_active=True,
                items=items_list
            )

        cart.items.all().delete()
        for key in ['checkout_data', 'user_address', 'producer_groups']:
            request.session.pop(key, None)

        return render(request, 'payment_success.html', {
            'order_id': order.order_id,
            'total': float(order.total_amount),
            'items': all_items,
            'order_date': order.created_at,
            'customer_name': get_display_name(request.user),
            'delivery_address': order.delivery_address if has_delivery else '',
            'delivery_postcode': order.delivery_postcode if has_delivery else '',
            'show_address': has_delivery,
            'user_email': request.user.email
        })