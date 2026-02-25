from django.db import models
from order_management.models import Order, SubOrderPerProducer
from producers.models import ProducerAccount


class PaymentTransaction(models.Model):
    """Record of payment attempt for an order"""
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('stripe_card', 'Stripe Card'),
        ('paypal', 'PayPal'),
        ('bank_transfer', 'Bank Transfer'),
    ]
    
    transaction_id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='transactions')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    
    payment_intent_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_charge_id = models.CharField(max_length=100, blank=True, null=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "payment_transactions"
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.payment_status}"


class ProducerPayout(models.Model):
    """Weekly payment settlements to producers"""
    
    PAYOUT_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    payout_id = models.AutoField(primary_key=True)
    producer = models.ForeignKey(ProducerAccount, on_delete=models.CASCADE, related_name='payouts')
    
    week_start_date = models.DateField()
    week_end_date = models.DateField()
    
    total_orders_value = models.DecimalField(max_digits=10, decimal_places=2)
    commission_deducted = models.DecimalField(max_digits=10, decimal_places=2)
    payout_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    payout_status = models.CharField(max_length=20, choices=PAYOUT_STATUS, default='pending')
    payout_reference = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = "producer_payouts"
        ordering = ['-week_start_date']
    
    def __str__(self):
        return f"Payout {self.payout_id}"


class PayoutOrderItem(models.Model):
    """Link payouts to specific suborders"""
    
    payout = models.ForeignKey(ProducerPayout, on_delete=models.CASCADE, related_name='order_items')
    suborder = models.ForeignKey(SubOrderPerProducer, on_delete=models.CASCADE)
    
    class Meta:
        db_table = "payout_order_items"