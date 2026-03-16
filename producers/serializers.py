from decimal import Decimal, InvalidOperation
from rest_framework import serializers
from product.models import Product, ProductCategory, Allergen, ProductAllergen
from user_accounts.models import ProducerAccount
from order_management.models import SubOrder, OrderItem

class ProductCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    category = serializers.PrimaryKeyRelatedField(queryset=ProductCategory.objects.all())
    description = serializers.CharField(allow_blank=True, required=False)
    price = serializers.CharField()  # accept "£3.50" or "3.50"
    unit = serializers.CharField(max_length=50)
    availability = serializers.CharField()
    stock = serializers.IntegerField(min_value=0)
    allergens = serializers.ListField(child=serializers.CharField(), allow_empty=True, required=False)
    harvest_date = serializers.DateField(required=False, allow_null=True)
    image = serializers.ImageField(required=False, allow_null=True)
    organic_certified = serializers.BooleanField(required=False, default=False)

    def validate_price(self, value):
        # Strip currency symbols/spaces/commas: "£3.50" -> "3.50"
        cleaned = (
            str(value)
            .replace("£", "")
            .replace("$", "")
            .replace(",", "")
            .strip()
        )
        try:
            dec = Decimal(cleaned)
        except (InvalidOperation, ValueError):
            raise serializers.ValidationError("Price must be a valid number (e.g., 3.50).")
        if dec < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        return dec

    def create(self, validated_data):
        request = self.context["request"]

        producer_account = ProducerAccount.objects.filter(user=request.user).first()
        if not producer_account:
            raise serializers.ValidationError({"producer": "Producer account not found for this user."})
        stock = validated_data.pop("stock")
        validated_data.pop("allergens", None)
        availability_text = (validated_data.pop("availability") or "").strip().lower()
        # allergens_value = validated_data.pop("allergens", "")
        # In case request is multipart (image upload) and allergens were sent as repeated keys
        # raw_list = request.data.getlist("allergens") if hasattr(request.data, "getlist") else []
        # if raw_list:  # prefer multipart list if present
        #   allergens_value = raw_list
        image = validated_data.pop("image", None)

        available_values = {"available", "in season (available)", "in season"}
        availability_status = availability_text in available_values
        organic_certified = validated_data.pop("organic_certified", False)
        product = Product.objects.create(
            producer=producer_account,
            stock_quantity=stock,
            availability_status=availability_status,
            organic_certified=organic_certified,
            image=image,
            **validated_data
        )

        return product
    
class ProductSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)
    allergens = serializers.ListField(child=serializers.CharField(),required=False,allow_empty=True)
    class Meta:
        model = Product
        fields = "__all__"

class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name")
    image = serializers.SerializerMethodField()
    class Meta:
        model = OrderItem
        fields = [
            "product_name",
            "quantity",
            "price_at_purchase",
            "image",
        ]
    def get_image(self, obj):
        if obj.product.image:
            return obj.product.image.url
        return None


class ProducerOrderSerializer(serializers.ModelSerializer):

    order_id = serializers.IntegerField(source="order.order_id")

    customer_name = serializers.SerializerMethodField()
    customer_contact = serializers.SerializerMethodField()

    delivery_address = serializers.CharField(source="order.delivery_address")
    
    created_at = serializers.DateTimeField(
        source="order.created_at",
        format="%d/%m/%Y"
    )
    delivery_type = serializers.SerializerMethodField()
    items = OrderItemSerializer(many=True, read_only=True)

    total_value = serializers.DecimalField(
        source="payout_amount",
        max_digits=10,
        decimal_places=2
    )

    class Meta:
        model = SubOrder
        fields = [
            "order_id",
            "customer_name",
            "customer_contact",
            "delivery_address",
            "delivery_type",
            "created_at",
            "delivery_date",
            "special_instruction",
            "items",
            "total_value",
            "status",
        ]

    def get_customer_name(self, obj):
        customer = obj.order.customer
        # Normal customer
        if customer.person:
            return f"{customer.person.first_name} {customer.person.last_name}"

        # Community group
        try:
            if customer.account_type == "community":
                return customer.communitygroup.organisation_name
        except:
            pass

        # Restaurant
        try:
            if customer.account_type == "restaurant":
                return customer.restaurant.organisation_name
        except:
            pass

        # Fallback
        return customer.user.email

    def get_customer_contact(self, obj):

        customer = obj.order.customer

        # Normal customer
        if customer.person and customer.person.phone:
            return customer.person.phone

        # Community group
        try:
            if customer.account_type == "community":
                return customer.communitygroup.phone
        except:
            pass

        # Restaurant
        try:
            if customer.account_type == "restaurant":
                return customer.restaurant.phone
        except:
            pass

        return ""
        
    def get_delivery_type(self, obj):
        if obj.delivery_date:
            return "Delivery"
        return "Collection"