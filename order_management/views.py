
# Create your views here.
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from user_accounts.models import CustomerAccount, Person, Address, ProducerAccount
import logging

logger = logging.getLogger(__name__)

def order_home(request):
        return render(request, "base.html")


def payment(request):
    return render(request, "payment.html")






from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from user_accounts.models import CustomerAccount, Person, Address

def multi_checkout(request):
    # Get cart from session
    cart_items_by_producer = request.session.get("cart_items_by_producer", {})
    
    # FOR TESTING: If cart is empty, create sample data
    if not cart_items_by_producer:
        class TestProducer:
            def __init__(self, id, name):
                self.id = id
                self.name = name
        
        cart_items_by_producer = {
            TestProducer(1, "Farm Fresh Organic"): [
                {"product": type('obj', (object,), {"name": "Organic Apples"}), 
                 "quantity": 2, "price": 3.50},
                {"product": type('obj', (object,), {"name": "Free Range Eggs"}), 
                 "quantity": 1, "price": 4.50},
            ],
            TestProducer(2, "Artisan Bakery"): [
                {"product": type('obj', (object,), {"name": "Sourdough Bread"}), 
                 "quantity": 2, "price": 5.99},
            ],
        }

    # Calculate 48‑hour minimum delivery date
    min_delivery_date = (timezone.now() + timedelta(hours=48)).date()

    producer_groups = []
    summary_items = []
    overall_subtotal = 0
    
    for producer, items in cart_items_by_producer.items():
        producer_subtotal = 0
        for item in items:
            item_total = float(item['price']) * int(item['quantity'])
            producer_subtotal += item_total
        
        producer_commission = round(producer_subtotal * 0.05, 2)
        producer_total = round(producer_subtotal * 1.05, 2)
        
        producer_groups.append({
            "producer": producer,
            "items": items,
            "min_delivery_date": min_delivery_date,
            "subtotal": round(producer_subtotal, 2),
            "commission": producer_commission,
            "total": producer_total,
        })
        
        summary_items.extend(items)
        overall_subtotal += producer_subtotal

    overall_commission = round(overall_subtotal * 0.05, 2)
    overall_total = round(overall_subtotal * 1.05, 2)

    # SIMPLE ADDRESS FETCHING
    user_address = None
    if request.user.is_authenticated:
        try:
            # Try to get customer account
            customer = CustomerAccount.objects.get(user=request.user)
            
            # Get person name
            if customer.person:
                full_name = f"{customer.person.first_name} {customer.person.last_name}"
                phone = customer.person.phone or ""
            else:
                full_name = request.user.email
                phone = ""
            
            # Get address
            if customer.address:
                street = customer.address.address_line
                postcode = customer.address.postcode
            else:
                street = "No address saved"
                postcode = ""
            
            user_address = {
                'full_name': full_name,
                'email': request.user.email,
                'phone': phone,
                'street': street,
                'postcode': postcode,
            }
        except CustomerAccount.DoesNotExist:
            # User logged in but not a customer
            user_address = {
                'full_name': request.user.email,
                'email': request.user.email,
                'phone': '',
                'street': 'Please create a customer profile',
                'postcode': '',
            }

    context = {
        "producer_groups": producer_groups,
        "summary_items": summary_items,
        "subtotal": round(overall_subtotal, 2),
        "commission": overall_commission,
        "total": overall_total,
        "user_address": user_address,
    }
    
    return render(request, "multi_checkout.html", context)