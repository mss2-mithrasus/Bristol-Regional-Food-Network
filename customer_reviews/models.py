from django.db import models

# Create your models here.
from user_accounts.models import CustomerAccount


class Review(models.Model):
    review_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(
        CustomerAccount,
        on_delete=models.CASCADE,
        db_column="customer_id"
    )
    product_id = models.IntegerField()
    rating = models.IntegerField()
    title = models.CharField(max_length=200)
    review = models.TextField()
    verified_purchase_status = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = "reviews"