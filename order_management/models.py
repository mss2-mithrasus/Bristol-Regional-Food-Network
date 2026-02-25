from django.db import models
from user_accounts.models import CustomerAccount
from producers.models import ProducerAccount
from product.models import Product
import uuid
from decimal import Decimal


class Order(models.Model):
    """Main customer order"""
    
    order_id = models.AutoField(primary_key=True)
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(CustomerAccount, on_delete=models.CASCADE, related_name='orders')
    
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    delivery_address = models.TextField()
    delivery_postcode = models.CharField(max_length=10)
    
    is_multi_vendor = models.BooleanField(default=False)
    payment_status = models.CharField(max_length=20, default='PENDING')
    payment_intent_id = models.CharField(max_length=100, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "orders"
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Order {self.order_number}"


class SubOrderPerProducer(models.Model):
    """Individual producer's portion of an order"""
    
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Ready', 'Ready'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    ]
    
    suborder_id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='suborders')
    producer = models.ForeignKey(ProducerAccount, on_delete=models.CASCADE, related_name='received_orders')
    
    delivery_date = models.DateField()
    special_instruction = models.TextField(null=True, blank=True)
    
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    payout_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    status_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "suborder_per_producer"
        ordering = ['delivery_date', 'created_at']
    
    def __str__(self):
        return f"SubOrder {self.suborder_id}"


class OrderItem(models.Model):
    """Individual products in an order"""
    
    order_item_id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    suborder = models.ForeignKey(SubOrderPerProducer, on_delete=models.CASCADE, related_name='items')
    
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    product_name = models.CharField(max_length=200)
    quantity = models.IntegerField()
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        db_table = "order_item"
    
    def get_subtotal(self):
        return self.price_at_purchase * self.quantity
    
    def __str__(self):
        return f"{self.quantity}x {self.product_name}"


class OrderStatusHistory(models.Model):
    """Audit trail for status changes"""
    
    history_id = models.AutoField(primary_key=True)
    suborder = models.ForeignKey(SubOrderPerProducer, on_delete=models.CASCADE, related_name='status_history')
    
    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    
    changed_by = models.ForeignKey(
        ProducerAccount,
        on_delete=models.SET_NULL,
        null=True,
        related_name='status_changes_made'
    )
    
    notes = models.TextField(blank=True)
    order_status_changed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "order_status_history"
        ordering = ['-order_status_changed_at']
    
    def __str__(self):
        return f"{self.old_status} → {self.new_status}"


class RecurringOrder(models.Model):
    """Template for recurring orders"""
    
    RECURRENCE_CHOICES = [
        ('weekly', 'Weekly'),
        ('fortnightly', 'Fortnightly'),
        ('monthly', 'Monthly'),
    ]
    
    recurring_order_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(CustomerAccount, on_delete=models.CASCADE, related_name='recurring_orders')
    
    recurrence_schedule = models.CharField(max_length=20, choices=RECURRENCE_CHOICES)
    next_order_date = models.DateField()
    active_status = models.BooleanField(default=True)
    
    delivery_address = models.TextField()
    delivery_postcode = models.CharField(max_length=10)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "recurring_order"
    
    def __str__(self):
        return f"Recurring Order {self.recurring_order_id}"


class RecurringOrderItem(models.Model):
    """Products in a recurring order template"""
    
    recurring_order = models.ForeignKey(RecurringOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    
    class Meta:
        db_table = "recurring_order_item"
    
    def __str__(self):
        return f"{self.quantity}x {self.product.name}"