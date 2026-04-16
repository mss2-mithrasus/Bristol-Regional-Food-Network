from decimal import Decimal, InvalidOperation
from rest_framework import serializers
from product.models import Product, ProductCategory, Allergen, ProductAllergen, SeasonalAvailability
from user_accounts.models import ProducerAccount
from order_management.models import SubOrder, OrderItem
from django.utils import timezone
from .models import SettlementReport, ProducerSettlementOrder, SurplusDiscount
import json
from datetime import timedelta
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
    best_before_date = serializers.DateField(required=False, allow_null=True)
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
            **validated_data
        )
        
        if image:
            product.image = image
            product.save()

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
# Micaiah added - 13-04-2026 - Surplus Serilizers
class SurplusDiscountSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    original_price = serializers.DecimalField(
        source="product.price",
        max_digits=8,
        decimal_places=2,
        read_only=True
    )
    discounted_price = serializers.SerializerMethodField()

    class Meta:
        model = SurplusDiscount
        fields = [
            "surplus_id",
            "product",
            "product_name",
            "original_price",
            "discount_percentage",
            "discounted_price",
            "note",
            "expiry_date",
            "status",
            "date_discount_created",
        ]

    def get_discounted_price(self, obj):
        if not obj.product:
            return None
        return round(float(obj.product.price) * (100 - obj.discount_percentage) / 100, 2)

    def validate_discount_percentage(self, value):
        if value < 10 or value > 50:
            raise serializers.ValidationError("Discount must be between 10% and 50%.")
        return value

    def validate_expiry_date(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("Expiry date must be in the future.")
        return value
    
    def validate(self, attrs):
        product = attrs.get("product")
        expiry_date = attrs.get("expiry_date")

        if product:
            earliest_fulfilment_date = timezone.now().date() + timedelta(days=2)

            if product.best_before_date:
                if timezone.now().date() > product.best_before_date:
                    raise serializers.ValidationError({
                        "product": "This product has passed its best before date and cannot be marked as surplus."
                    })

                if product.best_before_date < earliest_fulfilment_date:
                    raise serializers.ValidationError({
                        "product": "This product cannot be offered as a surplus deal because its best before date is earlier than the earliest customer fulfilment date."
                    })

                if expiry_date and expiry_date.date() > product.best_before_date:
                    raise serializers.ValidationError({
                        "expiry_date": "Surplus deal expiry cannot be later than the product's best before date."
                    })

        return attrs
    
# class OrderItemSerializer(serializers.ModelSerializer):
#     product_name = serializers.CharField(source="product.name")
#     image = serializers.SerializerMethodField()

#     class Meta:
#         model = OrderItem
#         fields = [
#             "product_name",
#             "quantity",
#             "price_at_purchase",
#             "image",
#         ]

#     def get_image(self, obj):
#         if obj.product.image:
#             return obj.product.image.url
#         return None

# Micaiah changed for surplus discount 
class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name")
    image = serializers.SerializerMethodField()
    original_price_at_purchase = serializers.SerializerMethodField()
    has_surplus_discount = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()
    original_line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "product_name",
            "quantity",
            "price_at_purchase",
            "original_price_at_purchase",
            "has_surplus_discount",
            "line_total",
            "original_line_total",
            "image",
        ]

    def get_image(self, obj):
        if obj.product.image:
            return obj.product.image.url
        return None

    def get_original_price_at_purchase(self, obj):
        original_price = getattr(obj, "original_price_at_purchase", None) or obj.price_at_purchase
        return float(original_price)

    def get_has_surplus_discount(self, obj):
        original_price = getattr(obj, "original_price_at_purchase", None) or obj.price_at_purchase
        return float(obj.price_at_purchase) != float(original_price)

    def get_line_total(self, obj):
        return float(obj.quantity * obj.price_at_purchase)

    def get_original_line_total(self, obj):
        original_price = getattr(obj, "original_price_at_purchase", None) or obj.price_at_purchase
        return float(obj.quantity * original_price)

class ProducerOrderSerializer(serializers.ModelSerializer):

    order_id = serializers.IntegerField(source="order.order_id")
    customer_name = serializers.SerializerMethodField()
    customer_contact = serializers.SerializerMethodField()
    delivery_address = serializers.CharField(source="order.delivery_address")
    created_at = serializers.DateTimeField(source="order.created_at", format="%d/%m/%Y")
    delivery_type = serializers.SerializerMethodField()
    items = OrderItemSerializer(many=True, read_only=True)
    #total_value = serializers.DecimalField(source="payout_amount", max_digits=10, decimal_places=2)
    # Micaiah changed for surplus discount
    total_value = serializers.DecimalField(source="subtotal", max_digits=10, decimal_places=2)
    # Change end     
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