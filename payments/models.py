from django.db import models


# ============================================================
# PAYMENT TRANSACTION
# ============================================================
class PaymentTransaction(models.Model):
    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCEEDED = 'succeeded', 'Succeeded'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'
    
    class PaymentMethod(models.TextChoices):
        CARD = 'card', 'Credit/Debit Card'
    
    transaction_id = models.AutoField(primary_key=True)
    
    order = models.ForeignKey(
        'order_management.Order',
        on_delete=models.CASCADE,
        related_name='payments',
        db_column='order_id'
    )
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='gbp')
    payment_method = models.CharField(max_length=50, choices=PaymentMethod.choices)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'payment_transactions'
    
    def __str__(self):
        return f"Payment {self.transaction_id} - {self.payment_status}"


# ============================================================
# COMMISSION
# ============================================================
class Commission(models.Model):
    class CommissionStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
    
    commission_id = models.AutoField(primary_key=True)
    
    order = models.ForeignKey(
        'order_management.Order',
        on_delete=models.CASCADE,
        related_name='commissions',
        db_column='order_id'
    )
    
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    producer_payout = models.DecimalField(max_digits=10, decimal_places=2)
    
    status = models.CharField(max_length=20, choices=CommissionStatus.choices, default=CommissionStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'commissions'
    
    def __str__(self):
        return f"Commission {self.commission_id} - £{self.commission_amount}"