from django.db import models

# Create your models here.

class ShoppingCart(models.Model):
    cart_id = models.AutoField(primary_key=True)
    user_id = models.IntegerField()  # FK placeholder, ideally link to User model
    created_at = models.DateTimeField(auto_now_add=True)
    cart_status = models.CharField(max_length=50)  # e.g., 'active', 'checked_out', 'abandoned'

    class Meta:
        managed = True
        db_table = "shopping_cart"

    def __str__(self):
        return f"Cart {self.cart_id} for User {self.user_id}"
    
# dummy product model for testing purposes
    
class Product(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="products/")

    class Meta:
        managed = True
        db_table = "product"

    def __str__(self):
        return self.name



class ShoppingCartItem(models.Model):
    cart_item_id = models.AutoField(primary_key=True)
    cart = models.ForeignKey(ShoppingCart, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    #cart_id = models.IntegerField()   # FK placeholder, ideally link to ShoppingCart
    #product_id = models.IntegerField()  # FK placeholder, ideally link to Product model
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        managed = True
        db_table = "shopping_cart_item"

    def __str__(self):
        return f"Item {self.product.name} in Cart {self.cart.cart_id}"
    

