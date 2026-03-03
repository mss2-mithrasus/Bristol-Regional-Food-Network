
from django.db import models
from django.conf import settings


# -----------------------------
# SURPLUS DISCOUNT
# -----------------------------
class SurplusDiscount(models.Model):
    surplus_id = models.AutoField(primary_key=True)

    product = models.ForeignKey(
        "product.Product",
        on_delete=models.CASCADE,null=True, blank=True,
        db_column="product_id",
        related_name="surplus_discounts",
    )

    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    expiry_date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=[("active", "active"), ("expired", "expired")],
        default="active",
    )

    date_discount_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = "surplus_discount"


# -----------------------------
# INVENTORY (Stock Change History)
# -----------------------------
class Inventory(models.Model):
    inventory_id = models.AutoField(primary_key=True)

    product = models.ForeignKey(
        "product.Product",
        on_delete=models.CASCADE,
        db_column="product_id", null=True, blank=True,
        related_name="inventory_history",
    )

    old_stock = models.PositiveIntegerField()
    new_stock = models.PositiveIntegerField()
    stock_time_change = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = "inventory"


# -----------------------------
# SETTLEMENT REPORT
# -----------------------------
class SettlementReport(models.Model):
    settlement_report_id = models.AutoField(primary_key=True)

    # Placeholder for now: use the main user model (works even if you later create ProducerAccount)
    producer = models.ForeignKey(
        "user_accounts.ProducerAccount",
        on_delete=models.CASCADE,
        db_column="producer_id",
        related_name="settlement_reports",
    )

    # Placeholder for now: transaction reference (later can become FK to a payments table)
    transaction_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_column="transaction_id",
        help_text="Payment transaction reference (placeholder until payments app exists).",
    )

    week_start = models.DateField()
    week_end = models.DateField()
    total_order_value = models.DecimalField(max_digits=10, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payout_amount = models.DecimalField(max_digits=10, decimal_places=2)

    payment_status = models.CharField(
        max_length=20,
        choices=[("Pending", "Pending"), ("Paid", "Paid")],
        default="Pending",
    )

    class Meta:
        managed = True
        db_table = "settlement_report"


# -----------------------------
# PRODUCER SETTLEMENT ORDER
# -----------------------------
class ProducerSettlementOrder(models.Model):
    settlement_order_id = models.AutoField(primary_key=True)

    settlement_report = models.ForeignKey(
        SettlementReport,
        on_delete=models.CASCADE,
        db_column="settlement_report_id",
        related_name="settlement_orders",
    )

    # Placeholder for now: store order id as integer.
    # Later: convert to ForeignKey once your Orders model exists.
    order_id = models.IntegerField(db_column="order_id")

    order_value = models.DecimalField(max_digits=10, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    producer_payout = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        managed = True
        db_table = "producer_settlement_order"


# -----------------------------
# FARM STORY
# -----------------------------
class FarmStory(models.Model):
    farm_story_id = models.AutoField(primary_key=True)

    # Placeholder: use AUTH_USER_MODEL
    producer = models.ForeignKey(
        "user_accounts.ProducerAccount",
        on_delete=models.CASCADE,
        db_column="producer_id",
        related_name="farm_stories",
    )

    title = models.CharField(max_length=200)
    content = models.TextField()
    image = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = "farm_story"


# -----------------------------
# RECIPES
# -----------------------------
class Recipe(models.Model):
    recipe_id = models.AutoField(primary_key=True)

    # Placeholder: use AUTH_USER_MODEL
    producer = models.ForeignKey(
        "user_accounts.ProducerAccount",
        on_delete=models.CASCADE,
        db_column="producer_id",
        related_name="recipes",
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    ingredients = models.TextField()
    instructions = models.TextField()
    seasonal_tag = models.CharField(max_length=100, null=True, blank=True)
    image = models.CharField(max_length=500, null=True, blank=True)
    date_recipe_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = "recipes"


# -----------------------------
# PRODUCTS ↔ RECIPES
# -----------------------------
class RecipeProduct(models.Model):
    recipe_product_id = models.AutoField(primary_key=True)

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        db_column="recipe_id",
        related_name="linked_products",
    )

    product = models.ForeignKey(
        "product.Product",
        on_delete=models.CASCADE,null=True, blank=True,
        db_column="product_id",
        related_name="linked_recipes",
    )

    class Meta:
        managed = True
        db_table = "products_recipes"
        constraints = [
            models.UniqueConstraint(fields=["recipe", "product"], name="unique_recipe_product_link")
        ]


# -----------------------------
# SAVED RECIPES (Customer Favourites)
# -----------------------------
class SavedRecipe(models.Model):
    saved_id = models.AutoField(primary_key=True)

    # Placeholder: use AUTH_USER_MODEL (later can become CustomerAccount)
    customer = models.ForeignKey(
        "user_accounts.CustomerAccount",
        on_delete=models.CASCADE,
        db_column="customer_id",
        related_name="saved_recipes",
    )

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        db_column="recipe_id",
        related_name="saved_by_customers",
    )

    class Meta:
        managed = True
        db_table = "saved_recipes"
        constraints = [
            models.UniqueConstraint(fields=["customer", "recipe"], name="unique_customer_recipe_save")
        ]


# -----------------------------
# EDUCATIONAL CONTENT
# -----------------------------
class EducationalContent(models.Model):
    article_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    body = models.TextField()
    image = models.CharField(max_length=500, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = "educational_content"
