from decimal import Decimal, InvalidOperation
from rest_framework import serializers
from product.models import Product, ProductCategory, Allergen, ProductAllergen, SeasonalAvailability
from user_accounts.models import ProducerAccount
import json

class ProductCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    category = serializers.PrimaryKeyRelatedField(queryset=ProductCategory.objects.all())
    description = serializers.CharField(allow_blank=True, required=False)
    price = serializers.CharField()  # accept "£3.50" or "3.50"
    unit = serializers.CharField(max_length=50)
    #availability = serializers.CharField()
    stock = serializers.IntegerField(min_value=0)
    allergens = serializers.CharField(required=False, allow_blank=True)
    harvest_date = serializers.DateField(required=False, allow_null=True)
    image = serializers.ImageField(required=False, allow_null=True)
    organic_certified = serializers.BooleanField(required=False, default=False)
    #added for seasonal data
    seasonal_type = serializers.CharField(required=False)
    season_start_date = serializers.DateField(required=False, allow_null=True)
    season_end_date = serializers.DateField(required=False, allow_null=True)

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
        
        allergens_data = validated_data.pop("allergens", [])
        try: 
            
            allergens_data = json.loads(allergens_data)
        except Exception:
            allergens_data = []
        
        
        stock = validated_data.pop("stock")
        #seasonal availability
        seasonal_type = validated_data.pop("seasonal_type", None)
        season_start_date = validated_data.pop("season_start_date", None)
        season_end_date = validated_data.pop("season_end_date", None)
        #availability_text = (validated_data.pop("availability") or "").strip().lower()
        image = validated_data.pop("image", None)
        #available_values = {"available", "in season (available)", "in season"}
        #availability_status = availability_text in available_values
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
    allergens = serializers.ListField(child=serializers.CharField(),required=False,allow_empty=True)
    class Meta:
        model = Product
        fields = "__all__"