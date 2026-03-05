from django.db import models

# Create your models here.
from django.db import models


# ============================================================
# ORDER
# ============================================================
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
        

# ============================================================
# SUBORDER
# ============================================================
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


# ============================================================
# ORDER STATUS HISTORY
# ============================================================
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


# ============================================================
# ORDER ITEM
# ============================================================
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
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        managed = True
        db_table = "order_item"

    def __str__(self):
        return f"OrderItem #{self.order_item_id}"