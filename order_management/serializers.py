from rest_framework import serializers
from .models import Cart, CartItem, Order, ProducerOrder, OrderItem, OrderStatusHistory
from products.serializers import ProductSerializer

# CART SERIALIZERS (TC-006)

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, source='get_subtotal')
    producer_name = serializers.CharField(source='product.producer.business_name', read_only=True)
    
    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_id', 'quantity', 'subtotal', 
                 'producer_name', 'added_at']
    
    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1")
        return value


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, 
                                    read_only=True, source='get_total')
    producer_groups = serializers.SerializerMethodField()
    
    class Meta:
        model = Cart
        fields = ['id', 'customer', 'items', 'total', 'producer_groups', 
                 'created_at', 'updated_at']
        read_only_fields = ['customer']
    
    def get_producer_groups(self, obj):
        """Group items by producer for multi-vendor awareness"""
        groups = {}
        for item in obj.items.all():
            producer_id = item.product.producer.id
            producer_name = item.product.producer.business_name
            
            if producer_id not in groups:
                groups[producer_id] = {
                    'producer_name': producer_name,
                    'items': []
                }
            
            groups[producer_id]['items'].append(CartItemSerializer(item).data)
        
        return groups


# ============================================
# ORDER SERIALIZERS (TC-007, TC-008)
# ============================================

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'product_price', 
                 'quantity', 'subtotal']
        read_only_fields = ['product_name', 'product_price', 'subtotal']
    
    def get_subtotal(self, obj):
        return obj.get_subtotal()


class ProducerOrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    producer_name = serializers.CharField(source='producer.business_name', read_only=True)
    producer_email = serializers.EmailField(source='producer.email', read_only=True)
    status_history = serializers.SerializerMethodField()
    
    class Meta:
        model = ProducerOrder
        fields = ['id', 'producer', 'producer_name', 'producer_email', 
                 'delivery_date', 'special_instructions', 'subtotal', 
                 'producer_payment', 'status', 'status_notes', 'items',
                 'status_history', 'created_at', 'updated_at']
        read_only_fields = ['producer', 'subtotal', 'producer_payment']
    
    def get_status_history(self, obj):
        return OrderStatusHistorySerializer(obj.status_history.all(), many=True).data


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    producer_orders = ProducerOrderSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    customer_email = serializers.EmailField(source='customer.email', read_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'order_number', 'customer', 'customer_name', 'customer_email',
                 'delivery_address', 'delivery_postcode', 'subtotal', 'commission', 
                 'total', 'status', 'payment_status', 'is_multi_vendor', 
                 'items', 'producer_orders', 'created_at', 'updated_at']
        read_only_fields = ['order_number', 'customer', 'subtotal', 'commission', 
                           'total', 'is_multi_vendor']


class CheckoutSerializer(serializers.Serializer):
    """Serializer for checkout process"""
    delivery_address = serializers.CharField()
    delivery_postcode = serializers.CharField(max_length=10)
    delivery_dates = serializers.DictField(
        child=serializers.DateField(),
        help_text="Dict of producer_id: delivery_date"
    )
    special_instructions = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        help_text="Dict of producer_id: instructions"
    )
    payment_method_id = serializers.CharField(
        help_text="Stripe payment method ID"
    )


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source='changed_by.get_full_name', read_only=True)
    
    class Meta:
        model = OrderStatusHistory
        fields = ['id', 'old_status', 'new_status', 'notes', 'changed_by', 
                 'changed_by_name', 'changed_at']