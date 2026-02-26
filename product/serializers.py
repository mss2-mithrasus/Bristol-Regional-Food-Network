from rest_framework import serializers
from .models import ProductCategory, ProductAllergen, Product, Allergen, SeasonalAvailability

User = get_user_model()

class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = [
            "category_id",
            "category_name",
        ]
        
        
class AllergenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Allergen
        fields = [
            "allergen_id",
            "name",
        ]
        
        
class SeasonalAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = SeasonalAvailability
        fields = [
            "seasonal_id",
            "season_start_date",
            "season_end_date",
            "is_year_round",
        ]

