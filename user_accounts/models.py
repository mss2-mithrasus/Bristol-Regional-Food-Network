from django.db import models

# Create your models here.
class UserAccount(models.Model):
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('producer', 'Producer'),
        ('admin', 'Admin'),
    ]
    user_id = models.AutoField(primary_key=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    date_joined = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = "user_account"


class CustomerAccount(models.Model):
    customer_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        UserAccount,
        on_delete=models.CASCADE,
        db_column="user_id"
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    delivery_address = models.TextField()
    postcode = models.CharField(max_length=10)

    class Meta:
        managed = True
        db_table = "customer_account"


class ProducerAccount(models.Model):
    producer_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        UserAccount,
        on_delete=models.CASCADE,
        db_column="user_id"
    )
    business_name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=200)
    address = models.TextField()
    postcode = models.CharField(max_length=10)

    class Meta:
        managed = True
        db_table = "producer_account"