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
    
    # Calculate CURRENT available stock (including all reservations)
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
        else:
            print(f"  Not notifying {alert.customer.email} - requested {alert.requested_quantity}, only {current_available} available")
    
    
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
        print(f"Notification sent to producer {producer.business_name} for order #{order.order_id}")
    
    return notifications_created