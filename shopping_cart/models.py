
from django.db import models


from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from product.models import Product
from decimal import Decimal, ROUND_HALF_UP
from producers.models import SurplusDiscount


    
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
    reserved_until = models.DateTimeField(null=True, blank=True)  # When reservation expires
    
    class Meta:
        db_table = "cart_item"
        unique_together = ['cart', 'product'] 
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
    
    
    def get_unit_price(self):
        # Looks if the status us active for surplus discount
        active_surplus = (
            SurplusDiscount.objects
            .filter(
                product=self.product,
                status="active",
                expiry_date__gte=timezone.now()  
            )
            .order_by("-date_discount_created")
            .first()
        )

        # If there is an active surplus deal, calculate the discounted price
        if active_surplus:
            discount_multiplier = Decimal("1.00") - (
                Decimal(active_surplus.discount_percentage) / Decimal("100")
            )
            # Return discounted price rounded to 2 decimal places
            return (self.product.price * discount_multiplier).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

        # If there is no active surplus deal, return the normal product price
        return self.product.price

    
    @property
    def unit_price(self):
        return self.get_unit_price()


    @property
    def subtotal(self):
        # Calculates subtotal using the correct unit price
        return self.quantity * self.get_unit_price()
    
    @property
    def is_reservation_active(self):
        """Check if reservation is still valid"""
        if not self.reserved_until:
            return False
        return timezone.now() < self.reserved_until
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