from django.db import models
from django.conf import settings


class SurplusDiscount(models.Model):
    surplus_id = models.AutoField(primary_key=True)
    product_id = models.IntegerField()
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    expiry_date = models.DateField()
    status = models.CharField(max_length=20)

    class Meta:
        managed = True
        db_table = "surplus_discount"


class Inventory(models.Model):
    inventory_id = models.AutoField(primary_key=True)
    product_id = models.IntegerField()
    stock_quantity = models.PositiveIntegerField()
    availability_status = models.CharField(max_length=20)
    old_stock = models.PositiveIntegerField(null=True, blank=True)
    new_stock = models.PositiveIntegerField(null=True, blank=True)
    stock_time_change = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = "inventory"


class SettlementReport(models.Model):
    settlement_report_id = models.AutoField(primary_key=True)
    producer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column="producer_id"
    )
    week_start = models.DateField()
    week_end = models.DateField()
    total_order_value = models.DecimalField(max_digits=10, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payout_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=20)

    class Meta:
        managed = True
        db_table = "settlement_report"


class FarmStory(models.Model):
    farm_story_id = models.AutoField(primary_key=True)
    producer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column="producer_id"
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    image_url = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = "farm_story"


class Recipe(models.Model):
    recipe_id = models.AutoField(primary_key=True)
    producer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column="producer_id"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    ingredients = models.TextField()
    instructions = models.TextField()
    seasonal_tag = models.CharField(max_length=100, null=True, blank=True)
    image_url = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        managed = True
        db_table = "recipes"


class RecipeProduct(models.Model):
    recipe_product_id = models.AutoField(primary_key=True)
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        db_column="recipe_id"
    )
    product_id = models.IntegerField()

    class Meta:
        managed = True
        db_table = "products_recipes"