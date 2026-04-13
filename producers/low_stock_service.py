# producers/low_stock_service.py
from django.utils import timezone
from notifications.models import ProducerNotification
from producers.models import LowStockAlert
from product.models import Product

def check_low_stock(product):
    """
    Check if a product is below threshold and create/update alerts
    """
    
    producer = product.producer
    threshold = int(product.low_stock_threshold) if product.low_stock_threshold else 10
    current_stock = int(product.stock_quantity) if product.stock_quantity else 0
    
    # Check if there's an existing active alert
    existing_alert = LowStockAlert.objects.filter(
        product=product,
        producer=producer,
        is_resolved=False
    ).first()
    
    # If stock is below threshold
    if current_stock <= threshold:
        
        if existing_alert:
            # Update existing alert with new stock value
            existing_alert.current_stock = current_stock
            existing_alert.is_active = True
            existing_alert.save()
        else:
            # Create new alert
            LowStockAlert.objects.create(
                product=product,
                producer=producer,
                current_stock=current_stock,
                threshold=threshold,
                is_active=True,
                is_resolved=False
            )
        
        # Send notification to producer - ALWAYS SEND, NO DUPLICATE CHECK
        send_low_stock_notification(product, current_stock, threshold)
        return True
    
    # If stock is above threshold and there was an alert, resolve it
    elif existing_alert and not existing_alert.is_resolved:
        existing_alert.is_resolved = True
        existing_alert.is_active = False
        existing_alert.resolved_at = timezone.now()
        existing_alert.save()
        
        # Send resolved notification
        send_low_stock_resolved_notification(product, current_stock)
    
    else:
        print(f"ℹ️ [DEBUG] Stock is above threshold, no alert needed")
    
    return False


def send_low_stock_notification(product, current_stock, threshold):
    """
    Send low stock notification to producer - ALWAYS sends, no duplicate check
    """
    
    producer_user = product.producer.user
    unit = product.unit if product.unit else "units"
    
    # Create notification
    try:
        notification = ProducerNotification.objects.create(
            recipient=producer_user,
            notification_type='low_stock',
            title=f"⚠️ Low Stock Alert: {product.name}",
            message=f"Your product '{product.name}' is running low! Current stock: {current_stock} {unit}. Threshold: {threshold}. Please restock soon to avoid order failures.",
            order=None,
            suborder=None,
            is_read=False,
            is_seen=False
        )
    except Exception as e:
        print(f" [DEBUG] Error creating notification: {e}")


def send_low_stock_resolved_notification(product, current_stock):
    """
    Send notification when low stock alert is resolved
    """
    producer_user = product.producer.user
    
    from notifications.models import ProducerNotification
    
    unit = product.unit if product.unit else "units"
    
    try:
        notification = ProducerNotification.objects.create(
            recipient=producer_user,
            notification_type='low_stock_resolved',
            title=f" Low Stock Resolved: {product.name}",
            message=f"Good news! '{product.name}' stock has been replenished. Current stock: {current_stock} {unit}.",
            order=None,
            suborder=None,
            is_read=False,
            is_seen=False
        )
    except Exception as e:
        print(f" [DEBUG] Error creating resolved notification: {e}")