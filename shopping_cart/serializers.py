from rest_framework import serializers
from .models import Cart, CartItem
from product.models import Product
from product.serializers import ProductSerializer
from django.utils import timezone 
from producers.models import SurplusDiscount
from producers.utils import is_product_valid_for_fulfilment, get_earliest_fulfilment_date

class CartItemSerializer(serializers.ModelSerializer):
    """Serializer for cart items"""
    
    product_details = ProductSerializer(source='product', read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    producer_name = serializers.CharField(read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.DecimalField(source='product.price', max_digits=8, decimal_places=2, read_only=True)
    product_image = serializers.ImageField(source='product.image', read_only=True)
    organic_certified = serializers.BooleanField(source='product.organic_certified', read_only=True)
    
    class Meta:
        model = CartItem
        fields = [
            'cart_item_id',
            'product',
            'product_details',
            'product_name',
            'product_price',
            'product_image',
            'quantity',
            'subtotal',
            'producer_name',
            'organic_certified',
            'added_at'
        ]
        read_only_fields = ['cart_item_id', 'added_at']


class CartSerializer(serializers.ModelSerializer):
    """Serializer for the entire cart"""
    
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = Cart
        fields = [
            'cart_id',
            'customer',
            'items',
            'total_items',
            'subtotal',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['cart_id', 'customer', 'created_at', 'updated_at']


class AddToCartSerializer(serializers.Serializer):
    """Serializer for adding items to cart"""
    
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=99)
    
   

    # Micaiah changed for best before checks
    def validate_product_id(self, value):
        try:
            product = Product.objects.get(product_id=value)
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found")

        today = timezone.now().date()
        earliest_fulfilment_date = get_earliest_fulfilment_date()

        if product.best_before_date and product.best_before_date < today:
            product.availability_status = False
            product.is_expired = True
            product.save(update_fields=["availability_status", "is_expired"])

            SurplusDiscount.objects.filter(
                product=product,
                status="active"
            ).update(status="expired")

            raise serializers.ValidationError(
                "This product has passed its best before date and can no longer be purchased."
            )

        if product.best_before_date and product.best_before_date < earliest_fulfilment_date:
            product.availability_status = False
            product.save(update_fields=["availability_status"])

            SurplusDiscount.objects.filter(
                product=product,
                status="active"
            ).update(status="cancelled")

            raise serializers.ValidationError(
                "This product cannot be purchased because its best before date is earlier than the earliest fulfilment date."
            )

        if not is_product_valid_for_fulfilment(product):
            raise serializers.ValidationError("This product is not available for fulfilment.")

        if not product.availability_status:
            raise serializers.ValidationError("Product not found or unavailable")

        if product.stock_quantity < 1:
            raise serializers.ValidationError("Product out of stock")

        return value


class UpdateCartItemSerializer(serializers.Serializer):
    """Serializer for updating cart item quantity"""
    
    quantity = serializers.IntegerField(min_value=0, max_value=99)
    
    def validate_quantity(self, value):
        if value == 0:
            return value
        return value