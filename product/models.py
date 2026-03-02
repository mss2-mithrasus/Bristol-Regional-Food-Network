from django.db import models
from django.conf import settings

class ProductCategory(models.Model):
    category_id = models.AutoField(primary_key=True)
    category_name = models.CharField(max_length=255)
    
    class Meta:
        
        db_table = "product_category"
        
    def __str__(self):
        return self.category_name
    
    
class Allergen(models.Model):
    allergen_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    
    class Meta:
        db_table = "allergen"
        
    def __str__(self):
        return self.name
    
    
    
class Product(models.Model):
    
    product_id = models.AutoField(primary_key=True)
    producer = models.ForeignKey("user_accounts.ProducerAccount", on_delete=models.CASCADE, related_name="products")
    
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE, related_name="products")
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.CharField(max_length=50)
    stock_quantity = models.PositiveIntegerField()
    availability_status = models.BooleanField(default=True)
    harvest_date = models.DateField(null=True, blank=True)
    organic_certified = models.BooleanField(default=False)
    image = models.ImageField(upload_to='product_images/', null=True, blank=True)
    
    allergens = models.ManyToManyField(
        Allergen, through="ProductAllergen", blank=True, related_name="products"
    )
    
    class Meta:
        managed = True
        db_table = "products"
        
    def __str__(self):
        return self.name
    

class SeasonalAvailability(models.Model):
    seasonal_id = models.AutoField(primary_key=True)
    
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="seasonal_availability"
    )
    
    season_start_date = models.DateField(null=True, blank=True)
    season_end_date = models.DateField(null=True, blank=True)
    is_year_round = models.BooleanField(default=False)
    
    class Meta:
        managed = True
        db_table = "seasonal_availability"
        
    def __str__(self):
        return str(self.product)
    

    
class ProductAllergen(models.Model):
    product_allergen_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    allergen = models.ForeignKey(Allergen, on_delete=models.CASCADE)
    description = models.TextField(blank=True)
    
    
    class Meta:
        managed = True
        db_table = "product_allergen"
        unique_together = ("product", "allergen")
        
    def __str__(self):
        return str(self.product)