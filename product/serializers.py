from rest_framework import serializers
from .models import ProductCategory, ProductAllergen, Product, Allergen, SeasonalAvailability
from producers.utils import get_active_surplus_deal, is_product_valid_for_fulfilment

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
    # Micaiah added - 13-04-2026 - Surplus discount 
    #active_surplus = serializers.SerializerMethodField()
    has_surplus_discount = serializers.SerializerMethodField()
    original_price = serializers.SerializerMethodField()
    discounted_price = serializers.SerializerMethodField()
    surplus_note = serializers.SerializerMethodField()
    discount_percentage = serializers.SerializerMethodField()
    surplus_expiry_date = serializers.SerializerMethodField()
    # End 
    class Meta:
        model = Product
        fields = [
            "product_id",
            "name",
            "description",
            "price",
            "unit",
            "availability_status",
            "is_expired",
            "producer_name",
            "category",
            "image",
            "allergens",
            "stock_quantity",
            "organic_certified",
            "seasonal_availability",
            "low_stock_threshold", 
            "best_before_date",
            "has_surplus_discount",
            "original_price",
            "discounted_price",
            "surplus_note",
            "discount_percentage",
            "surplus_expiry_date",
            
        ]
        
    def get_producer_name(self, obj):
        return obj.producer.business_name
    
    # Micaiah added - 13-04-2026 - Surplus discount
    def _get_active_deal(self, obj):
        if not is_product_valid_for_fulfilment(obj):
            return None
        return get_active_surplus_deal(obj)

    def get_has_surplus_discount(self, obj):
        return self._get_active_deal(obj) is not None

    def get_original_price(self, obj):
        return obj.price

    def get_discounted_price(self, obj):
        deal = self._get_active_deal(obj)
        if not deal:
            return obj.price
        return round(float(obj.price) * (100 - deal.discount_percentage) / 100, 2)

    def get_surplus_note(self, obj):
        deal = self._get_active_deal(obj)
        return deal.note if deal else ""

    # def get_surplus_discount_percentage(self, obj):
    #     deal = self._get_active_deal(obj)
    #     return deal.discount_percentage if deal else None
    def get_discount_percentage(self, obj):
        deal = self._get_active_deal(obj)
        return deal.discount_percentage if deal else None
    def get_surplus_expiry_date(self, obj):
        deal = self._get_active_deal(obj)
        return deal.expiry_date if deal else None
       
    

    