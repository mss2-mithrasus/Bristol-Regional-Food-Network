from rest_framework import serializers
from .models import ProductCategory, ProductAllergen, Product, Allergen, SeasonalAvailability


# these serializers will convert the models into JSON and JSON to the model

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


# serializer for the products page that will contain all the products with all the relevant information

class ProductSerializer(serializers.ModelSerializer):
    category = ProductCategorySerializer(read_only=True)

    allergens = AllergenSerializer(many=True, read_only=True)
    
    # comes from producer_account.business_name 
    producer_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            "product_id",
            "name",
            "description",
            "price",
            "unit",
            "availability_status",
            "producer_name",
            "category",
            "image",
            "allergens",
            
        ]
        
    def get_producer_name(self, obj):
       
        if hasattr(obj.producer, "produceraccount"):
            return obj.producer.produceraccount.business_name
       
    
    
    