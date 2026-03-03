from rest_framework import serializers
from .models import ShoppingCartItem


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = ShoppingCartItem
        fields = [
            "cart_item_id",
            "product",
            "product_name",
            "quantity",
            "unit_price",
            "subtotal",
        ]

    def get_subtotal(self, obj):
        return obj.unit_price * obj.quantity
    

#------------
# shopping_cart/serializers.py
from rest_framework import serializers
from .models import ShoppingCartItem

class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = ShoppingCartItem
        fields = ["id", "product_name", "quantity", "unit_price", "subtotal"]

    def get_subtotal(self, obj):
        return obj.subtotal()