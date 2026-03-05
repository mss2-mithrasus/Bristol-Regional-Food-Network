from django.db import models

# Create your models here.
from django.conf import settings
from product.models import Product

class Cart(models.Model):
    """Shopping cart for each customer"""
    
    cart_id = models.AutoField(primary_key=True)
    customer = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='cart'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "shopping_cart"
    
    def __str__(self):
        return f"Cart for {self.customer.email}"
    
    @property
    def total_items(self):
        """Get total number of items in cart"""
        return sum(item.quantity for item in self.items.all())
    
    @property
    def subtotal(self):
        """Calculate cart subtotal"""
        return sum(item.subtotal for item in self.items.all())
    
    def get_items_grouped_by_producer(self):
        """Group cart items by producer for checkout"""
        items_by_producer = {}
        for item in self.items.select_related('product__producer').all():
            producer = item.product.producer
            try:
                producer_name = item.product.producer.produceraccount.business_name
            except:
                producer_name = "Unknown Producer"
            
            if producer not in items_by_producer:
                items_by_producer[producer] = {
                    'producer_id': producer.id,
                    'producer_name': producer_name,
                    'items': [],
                    'subtotal': 0
                }
            
            items_by_producer[producer]['items'].append(item)
            items_by_producer[producer]['subtotal'] += item.subtotal
        
        return items_by_producer


class CartItem(models.Model):
    """Individual items in shopping cart"""
    
    cart_item_id = models.AutoField(primary_key=True)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "cart_item"
        unique_together = ['cart', 'product'] 
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
    
    @property
    def subtotal(self):
        """Calculate item subtotal"""
        return self.quantity * self.product.price
    
    @property
    def producer_name(self):
        """Get producer name for this item"""
        try:
            # Try to get producer account
            if hasattr(self.product, 'producer'):
                producer = self.product.producer
                if hasattr(producer, 'produceraccount'):
                    return producer.produceraccount.business_name
                elif hasattr(producer, 'business_name'):
                    return producer.business_name
                elif hasattr(producer, 'get_full_name'):
                    return producer.get_full_name()
            return "Unknown Producer"
        except Exception as e:
            print(f"Error getting producer name: {e}")
            return "Unknown Producer"