from django.db import models
from user_accounts.models import CustomerAccount, ProducerAccount
from product.models import Product


class Order(models.Model):

    class OrderStatus(models.TextChoices):
        PENDING = "Pending"
        CONFIRMED = "Confirmed"
        READY = "Ready"
        DELIVERED = "Delivered"

    order_id = models.AutoField(primary_key=True)

    customer = models.ForeignKey(
        "user_accounts.CustomerAccount",
        on_delete=models.CASCADE,
        db_column="customer_id",
        related_name="orders",
    )

    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)

    delivery_address = models.CharField(max_length=255)
    delivery_postcode = models.CharField(max_length=20)

    order_status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = "orders"

    def __str__(self):
        return f"Order #{self.order_id}"
        


class SubOrder(models.Model):

    class SubOrderStatus(models.TextChoices):
        PENDING = "Pending"
        CONFIRMED = "Confirmed"
        READY = "Ready"
        DELIVERED = "Delivered"

    suborder_id = models.AutoField(primary_key=True)

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        db_column="order_id",
        related_name="suborders",
    )

    producer = models.ForeignKey(
        "user_accounts.ProducerAccount",
        on_delete=models.CASCADE,
        db_column="producer_id",
        related_name="producer_suborders",
    )

    delivery_date = models.DateField(null=True, blank=True)
   
    class FulfillmentMethod(models.TextChoices):
        DELIVERY = "delivery", "Delivery"
        COLLECTION = "collection", "Collection"
    
    fulfillment_method = models.CharField(
        max_length=10,
        choices=FulfillmentMethod.choices,
        default=FulfillmentMethod.DELIVERY,
    )
    
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    payout_amount = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(
        max_length=20,
        choices=SubOrderStatus.choices,
        default=SubOrderStatus.PENDING,
    )

    special_instruction = models.TextField(null=True, blank=True)
    

    class Meta:
        managed = True
        db_table = "suborder"

    def __str__(self):
        return f"SubOrder #{self.suborder_id}"


class OrderStatusHistory(models.Model):
    history_id = models.AutoField(primary_key=True)

    suborder = models.ForeignKey(
        SubOrder,
        on_delete=models.CASCADE,
        db_column="suborder_id",
        related_name="status_history",
    )

    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)

    stock_time_change = models.ForeignKey(
        "user_accounts.ProducerAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="producer_id",
    )

    order_status_changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = "order_status_history"

    def __str__(self):
        return f"StatusHistory #{self.history_id}"



class OrderItem(models.Model):
    order_item_id = models.AutoField(primary_key=True)

    suborder = models.ForeignKey(
        SubOrder,
        on_delete=models.CASCADE,
        db_column="suborder_id",
        related_name="items",
    )

    product = models.ForeignKey(
        "product.Product",
        on_delete=models.CASCADE,
        db_column="product_id",
    )

    quantity = models.PositiveIntegerField()
    #price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)

    # stores the normal/original price before any surplus discount
    original_price_at_purchase = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    class Meta:
        managed = True
        db_table = "order_item"

    def __str__(self):
        return f"OrderItem #{self.order_item_id}"
    

class RecurringTemplate(models.Model):
    RECURRENCE_CHOICES = [
        ('weekly', 'Weekly'),
        ('fortnightly', 'Fortnightly'),
        ('monthly', 'Monthly'),
    ]
    template_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(
        'user_accounts.CustomerAccount',
        on_delete=models.CASCADE,
        db_column="customer_id",
        related_name="recurring_templates",
    )
    name = models.CharField(max_length=255, blank=True, help_text="Optional name for this recurring order")
    recurrence = models.CharField(max_length=20, choices=RECURRENCE_CHOICES, default='weekly')
    delivery_weekday = models.IntegerField(help_text="0=Monday, 1=Tuesday, ..., 6=Sunday")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    items = models.JSONField()  # list of {product_id, quantity}
    created_at = models.DateTimeField(auto_now_add=True)
    
    def get_delivery_weekday_display(self):
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return weekdays[self.delivery_weekday]

    class Meta:
        db_table = "recurring_template"

    def __str__(self):
        return f"RecurringTemplate #{self.template_id} - {self.customer.user.email}"


class RecurringOrderInstance(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('generated', 'Generated'),
        ('skipped', 'Skipped'),
        ('cancelled', 'Cancelled'),
    ]
    instance_id = models.AutoField(primary_key=True)
    template = models.ForeignKey(RecurringTemplate, on_delete=models.CASCADE, related_name="instances")
    order = models.OneToOneField('Order', on_delete=models.CASCADE, related_name="recurring_instance")
    scheduled_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    last_stock_alert_sent = models.DateTimeField(null=True, blank=True)
    class Meta:
        db_table = "recurring_order_instance"
        unique_together = [('template', 'scheduled_date')]

    def __str__(self):
        return f"Instance #{self.instance_id} for template {self.template.template_id}"