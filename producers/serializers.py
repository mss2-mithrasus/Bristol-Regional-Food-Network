from decimal import Decimal, InvalidOperation
from rest_framework import serializers
from product.models import Product, ProductCategory, Allergen, ProductAllergen, SeasonalAvailability
from user_accounts.models import ProducerAccount
from order_management.models import SubOrder, OrderItem
from .models import SettlementReport, ProducerSettlementOrder
import json

class DashboardOrderSerializer(serializers.ModelSerializer):

    id = serializers.IntegerField(source="order.order_id")
    customer = serializers.SerializerMethodField()
    items = serializers.SerializerMethodField()

    class Meta:
        model = SubOrder
        fields = ["id", "customer", "items", "status"]

    def get_customer(self, obj):
        customer = obj.order.customer

        if customer.person:
            return f"{customer.person.first_name} {customer.person.last_name}"

        if customer.account_type == "community":
            return customer.communitygroup.organisation_name

        if customer.account_type == "restaurant":
            return customer.restaurant.organisation_name

        return customer.user.email

    def get_items(self, obj):
        return ", ".join(
            f"{i.product.name} x{i.quantity}"
            for i in obj.items.all()
        )


class ProductCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    category = serializers.PrimaryKeyRelatedField(queryset=ProductCategory.objects.all())
    description = serializers.CharField(allow_blank=True, required=False)
    price = serializers.CharField()
    unit = serializers.CharField(max_length=50)
    stock = serializers.IntegerField(min_value=0)
    allergens = serializers.CharField(required=False, allow_blank=True)
    harvest_date = serializers.DateField(required=False, allow_null=True)
    image = serializers.ImageField(required=False, allow_null=True)
    organic_certified = serializers.BooleanField(required=False, default=False)
    seasonal_type = serializers.CharField(required=False)
    season_start_date = serializers.DateField(required=False, allow_null=True)
    season_end_date = serializers.DateField(required=False, allow_null=True)

    def validate_price(self, value):
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

        allergens_data = validated_data.pop("allergens", [])
        try:
            allergens_data = json.loads(allergens_data)
        except Exception:
            allergens_data = []

        stock = validated_data.pop("stock")
        seasonal_type = validated_data.pop("seasonal_type", None)
        season_start_date = validated_data.pop("season_start_date", None)
        season_end_date = validated_data.pop("season_end_date", None)
        image = validated_data.pop("image", None)
        organic_certified = validated_data.pop("organic_certified", False)

        product = Product.objects.create(
            producer=producer_account,
            stock_quantity=stock,
            availability_status=True,
            organic_certified=organic_certified,
            image=image,
            **validated_data
        )

        if seasonal_type == "available_yearly":
            SeasonalAvailability.objects.create(
                product=product, is_year_round=True
            )
        elif seasonal_type == "seasonal":
            SeasonalAvailability.objects.create(
                product=product,
                season_start_date=season_start_date,
                season_end_date=season_end_date,
                is_year_round=False
            )

        print("allergen data:", allergens_data)
        for allg in allergens_data:
            if isinstance(allg, dict):
                name = allg.get("name")
                description = allg.get("description", "")
            else:
                name = allg
                description = ""

            allergen_object, _ = Allergen.objects.get_or_create(name=name)
            ProductAllergen.objects.create(
                product=product,
                allergen=allergen_object,
                description=description
            )

        return product


class ProductSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)
    allergens = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)

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
    created_at = serializers.DateTimeField(source="order.created_at", format="%d/%m/%Y")
    delivery_type = serializers.SerializerMethodField()
    items = OrderItemSerializer(many=True, read_only=True)
    total_value = serializers.DecimalField(source="payout_amount", max_digits=10, decimal_places=2)
    special_instruction = serializers.SerializerMethodField()

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
        try:
            customer = obj.order.customer

            if customer.person:
                return f"{customer.person.first_name} {customer.person.last_name}"

            try:
                if customer.account_type == "community":
                    return customer.communitygroup.organisation_name
            except Exception:
                pass

            try:
                if customer.account_type == "restaurant":
                    return customer.restaurant.organisation_name
            except Exception:
                pass

            return customer.user.email
        except Exception:
            return "Unknown Customer"

    def get_customer_contact(self, obj):
        try:
            customer = obj.order.customer

            if customer.person and customer.person.phone:
                return customer.person.phone

            try:
                if customer.account_type == "community":
                    return customer.communitygroup.phone
            except Exception:
                pass

            try:
                if customer.account_type == "restaurant":
                    return customer.restaurant.phone
            except Exception:
                pass

            return customer.user.email
        except Exception:
            return "No contact info"

    def get_delivery_type(self, obj):
        if obj.delivery_date:
            return "Delivery"
        return "Collection"
    
    def get_special_instruction(self, obj):
        return obj.special_instruction or ""
    
class ProducerSettlementOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProducerSettlementOrder
        fields = [
            "order_id",
            "order_value",
            "commission_amount",
            "producer_payout",
        ]


class SettlementReportSerializer(serializers.ModelSerializer):
    settlement_orders = ProducerSettlementOrderSerializer(many=True)

    class Meta:
        model = SettlementReport
        fields = [
            "settlement_report_id",
            "producer",
            "transaction_id",
            "week_start",
            "week_end",
            "total_order_value",
            "commission_amount",
            "payout_amount",
            "payment_status",
            "settlement_orders",
        ]