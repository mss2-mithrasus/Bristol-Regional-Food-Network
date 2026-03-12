from django.db import models

# Create your models here.
from django.db import models
from django.conf import settings
from django.utils import timezone
from product.models import Product

class StockAlert(models.Model):
    """
    When a customer wants to be notified when an out-of-stock item becomes available
    """
    alert_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='stock_alerts'
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_alerts')
    requested_quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    notified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = "stock_alerts"
        unique_together = ['customer', 'product']  # One alert per product per customer
    
    def __str__(self):
        return f"{self.customer.email} wants {self.requested_quantity} x {self.product.name}"


class Notification(models.Model):
    """
    Notifications sent to customers
    """
    NOTIFICATION_TYPES = [
        ('stock_available', 'Stock Available'),
        ('price_drop', 'Price Drop'),
        ('order_update', 'Order Update'),
        ('general', 'General'),
    ]
    
    notification_id = models.AutoField(primary_key=True)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='notifications'
    )
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Related objects (optional)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    alert = models.ForeignKey(StockAlert, on_delete=models.SET_NULL, null=True, blank=True)
    
    is_read = models.BooleanField(default=False)
    is_seen = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "notifications"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.recipient.email} - {self.title}"