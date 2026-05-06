from django.utils import timezone
from .models import Notification, StockAlert
from .models import ProducerNotification
from order_management.models import SubOrder
from shopping_cart.models import CartItem
from django.db.models import Sum

def notify_stock_available(product):
    """
    Notify customers only when their requested quantity becomes available
    """
    
    # Calculate current available stock (including all reservations)
    from shopping_cart.utils import get_available_stock
    current_available = get_available_stock(product, exclude_user=None)
    
    # Get all active alerts for this product
    active_alerts = StockAlert.objects.filter(
        product=product,
        is_active=True
    ).select_related('customer')
    
    notifications_created = 0
    
    for alert in active_alerts:
        # Only notify if the requested quantity is now available
        if current_available >= alert.requested_quantity:
        
            # Create notification
            notification = Notification.objects.create(
                recipient=alert.customer,
                notification_type='stock_available',
                title=f'{product.name} is back in stock!',
                message=f'Good news! {alert.requested_quantity} x {product.name} is now available. Click here to shop now.',
                product=product,
                alert=alert,
                is_read=False,
                is_seen=False
            )
            
            # Mark alert as notified
            alert.is_active = False
            alert.notified_at = timezone.now()
            alert.save()
            
            notifications_created += 1
    
    return notifications_created


def notify_producers_new_order(order):
    """
    Send notifications to all producers when a new order is placed
    """
    notifications_created = 0
    
    # Get all suborders for this order
    suborders = SubOrder.objects.filter(order=order).select_related('producer')
    
    for suborder in suborders:
        producer = suborder.producer
        producer_user = producer.user  # Get the user account for the producer
        
        # Count items in this suborder
        item_count = suborder.items.count()
        
        # Create notification
        notification = ProducerNotification.objects.create(
            recipient=producer_user,
            notification_type='new_order',
            title=f'New Order #{order.order_id} Received!',
            message=f'You have a new order with {item_count} item(s). Total: £{suborder.subtotal}',
            order=order,
            suborder=suborder,
            is_read=False,
            is_seen=False
        )
        
        notifications_created += 1
    
    return notifications_created


def notify_customers_surplus_deal(product, discount_percentage):
    """
    Send notifications to customers who have shown interest in this producer/product
    This matches the test case requirement: "customers receive notifications about surplus deals from favourite producers"
    """
    from user_accounts.models import CustomerAccount
    from .models import StockAlert
    
    notifications_created = 0
    
    # 1. Customers who have purchased any product from this producer (favourite producer)
    customers_who_bought_from_producer = CustomerAccount.objects.filter(
        user__is_active=True,
        orders__suborders__producer=product.producer
    ).distinct()
    
    # 2. Customers who purchased this specific product
    customers_who_bought_this_product = CustomerAccount.objects.filter(
        user__is_active=True,
        orders__suborders__items__product=product
    ).distinct()
    
    # 3. Customers who have this product in their cart
    customers_in_cart = CustomerAccount.objects.filter(
        user__is_active=True,
        user__cart__items__product=product
    ).distinct()
    
    # 4. Customers who have set a stock alert for this product
    customers_on_alert = StockAlert.objects.filter(
        product=product,
        is_active=True
    ).select_related('customer')
    
    # Combine all customers
    all_customers = set()
    
    for customer in customers_who_bought_from_producer:
        all_customers.add(customer.user)
    
    for customer in customers_who_bought_this_product:
        all_customers.add(customer.user)
    
    for customer in customers_in_cart:
        all_customers.add(customer.user)
    
    for alert in customers_on_alert:
        all_customers.add(alert.customer)
    
    # Send notification to each customer
    for customer_user in all_customers:
        try:
            notification = Notification.objects.create(
                recipient=customer_user,
                notification_type='surplus_available',
                title=f'Surprise! {product.name} on Surplus Deal!',
                message=f'Great news! {product.name} is now available with {discount_percentage}% off! Limited time offer while stocks last.',
                product=product,
                alert=None,
                is_read=False,
                is_seen=False
            )
            notifications_created += 1
        except Exception as e:
            pass
    
    return notifications_created