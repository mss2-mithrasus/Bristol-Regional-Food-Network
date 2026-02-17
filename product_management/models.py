from django.db import models
from user.models import User
from product_catalog.models import Category


# Create your models here.

class Product(models.Model):
    # define atttibutes
    producer = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    product_name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.CharField(max_length=50)
    stock_quantity = models.IntegerField()
    harvest_data = models.DateField()
    image = models.ImageField(upload_to='products/')
    
    
