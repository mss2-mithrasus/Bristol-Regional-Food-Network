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

# ❌ REMOVED: send_order_confirmation_email function

def payment_success(request):
    payment_intent_id = request.GET.get('payment_intent')
    
    # Get checkout data from session
    checkout_data = request.session.get('checkout_data', {})
    user_address = request.session.get('user_address', {})
    producer_groups = request.session.get('producer_groups', [])
    
    total = float(checkout_data.get('total', 0))
    commission = round(total * 0.05, 2)
    
    # Get the cart
    cart = Cart.objects.get(customer=request.user)
    
    # Create Order
    order = Order.objects.create(
        customer=request.user.customeraccount,
        total_amount=total,
        commission_amount=commission,
        delivery_address=user_address.get('street', ''),
        delivery_postcode=user_address.get('postcode', ''),
        order_status='Pending'
    )
    
    # Create SubOrders and collect items for receipt
    all_items = []
    for group in producer_groups:
        producer_id = group['producer']['id']
        producer_data = checkout_data.get('producer_data', {})
        date_key = f'producer_{producer_id}_delivery_date'
        delivery_date = producer_data.get(date_key, None)
        
        producer = ProducerAccount.objects.get(id=producer_id)
        subtotal = float(group['subtotal'])
        producer_total = float(group['total'])
        
        suborder = SubOrder.objects.create(
            order=order,
            producer=producer,
            delivery_date=delivery_date if delivery_date else None,
            subtotal=subtotal,
            payout_amount=producer_total,
            status='Pending',
        )
        
        for item_data in group['items']:
            product = Product.objects.get(product_id=item_data['product_id'])
            OrderItem.objects.create(
                suborder=suborder,
                product=product,
                quantity=item_data['quantity'],
                price_at_purchase=item_data['price']
            )
            all_items.append({
                'name': item_data['product_name'],
                'quantity': item_data['quantity'],
                'price': item_data['price'],
                'unit': item_data.get('unit', ''),
                'image': item_data.get('image', None),
                'producer': producer.business_name
            })
    
    # ❌ REMOVED: send_order_confirmation_email call
    
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
    
    # Clear cart and session
    cart.items.all().delete()
    session_keys = ['checkout_data', 'user_address', 'producer_groups']
    for key in session_keys:
        if key in request.session:
            del request.session[key]
    
    # Show success page with receipt
    return render(request, 'payment_success.html', {
        'order_id': order.order_id,
        'total': total,
        'items': all_items,
        'order_date': timezone.now(),
        'customer_name': request.user.get_full_name() or request.user.email,
        'delivery_address': user_address.get('street', ''),
        'delivery_postcode': user_address.get('postcode', ''),
        'user_email': request.user.email
    })