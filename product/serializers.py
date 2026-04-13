from rest_framework import serializers
from .models import ProductCategory, ProductAllergen, Product, Allergen, SeasonalAvailability


# these serializers will convert the models into JSON and JSON to the model

class ProductCategorySerializer(serializers.ModelSerializer):
    
    image = serializers.SerializerMethodField()
    class Meta:
        model = ProductCategory
        fields = [
            "category_id",
            "category_name",
            "image",
        ]
        
        
    def get_image(self,obj):
        # mapping the category names to their corresponding images
        category_images = {
            "Vegetables": "images/carrot.png",
            "Dairy": "images/milk.png",
            "Bakery": "images/bread.png",
            "Preserves": "images/jam-jar.png",
            "Seasonal Specialities": "images/pumpkin.png"
        }
        return category_images.get(obj.category_name)
        
        
class AllergenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Allergen
        fields = [
           
            "name"
        ]
        
class ProductAllergenSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="allergen.name", read_only=True)
    class Meta:
        model = ProductAllergen
        fields = [ 
                 
                  "name",
                  "description",
                  
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

    allergens = ProductAllergenSerializer(source="productallergen_set", many=True,read_only=True)
    
    # comes from producer_account.business_name 
    producer_name = serializers.SerializerMethodField()
    
    #seasonal availability 
    seasonal_availability = SeasonalAvailabilitySerializer(
        
        many=True,
        read_only=True
    )
    
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
            "stock_quantity",
            "organic_certified",
            "seasonal_availability",
            "low_stock_threshold", 
            
        ]
        
    def get_producer_name(self, obj):
       
        
        return obj.producer.business_name
       
    

    