from django.db import models
from django.conf import settings
from product.models import Product  # correct import



class ShoppingCart(models.Model):
    cart_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carts"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    cart_status = models.CharField(max_length=50, default="active")

    class Meta:
        db_table = "shopping_cart"

    def __str__(self):
        return f"Cart {self.cart_id} for {self.user.email}"


class ShoppingCartItem(models.Model):
    cart_item_id = models.AutoField(primary_key=True)
    cart = models.ForeignKey(
        ShoppingCart,
        on_delete=models.CASCADE,
        related_name="items"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="cart_items"
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "shopping_cart_item"

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"