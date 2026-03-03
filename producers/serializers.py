from decimal import Decimal, InvalidOperation
from rest_framework import serializers
from product.models import Product, ProductCategory, Allergen, ProductAllergen
from user_accounts.models import ProducerAccount

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
        availability_text = (validated_data.pop("availability") or "").strip().lower()
        allergens_value = validated_data.pop("allergens", "")
        # In case request is multipart (image upload) and allergens were sent as repeated keys
        raw_list = request.data.getlist("allergens") if hasattr(request.data, "getlist") else []
        if raw_list:  # prefer multipart list if present
            allergens_value = raw_list
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

        
        if isinstance(allergens_value, list):
            allergen_names = [str(x).strip() for x in allergens_value if str(x).strip()]
            allergens_text = ", ".join(allergen_names)
        else:
            allergens_text = str(allergens_value or "").strip()
            cleaned = allergens_text.lower().replace("contains", "").strip()
            allergen_names = [p.strip() for p in cleaned.split(",") if p.strip()] or ([cleaned] if cleaned else [])

        # Save allergens via through model (with description)
        if allergen_names:
            for name in allergen_names:
                allergen_obj, _ = Allergen.objects.get_or_create(name=name.lower())
                ProductAllergen.objects.get_or_create(
                    product=product,
                    allergen=allergen_obj,
                    defaults={"description": allergens_text}
                )

        return product
    
class ProductSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)
    allergens = serializers.ListField(child=serializers.CharField(),required=False,allow_empty=True)
    class Meta:
        model = Product
        fields = "__all__"