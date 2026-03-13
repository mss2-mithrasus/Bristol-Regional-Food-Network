from django.utils import timezone
from .models import Notification, StockAlert
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