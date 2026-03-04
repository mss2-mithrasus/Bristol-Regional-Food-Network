# Micaiah Palha - 23033423
from django.db import models
from django.contrib.auth.models import AbstractUser
import hashlib


# USER (Authentication only)

class User(AbstractUser):
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    username = None
    email = models.EmailField(unique=True)

    USER_ROLE_CHOICES = [
        ("customer", "Customer"),
        ("producer", "Producer"),
        ("admin", "Admin"),
    ]
    role = models.CharField(max_length=20, choices=USER_ROLE_CHOICES)

    date_created = models.DateTimeField(auto_now_add=True)
    # Used for soft deleting user account
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    reason_for_deleting = models.CharField(max_length=255, null=True, blank=True)
    deleted_by_user = models.BooleanField(default=False)

    class Meta:
        db_table = "user_account"

    def __str__(self):
        return f"{self.email} ({self.role})"


# PERSON (Contact details)

class Person(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = "person"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"



# ADDRESS 
class Address(models.Model):
    address_line = models.CharField(max_length=255)
    postcode = models.CharField(max_length=20)

    class Meta:
        db_table = "address"

    def __str__(self):
        return f"{self.address_line}, {self.postcode}"


# CUSTOMER ACCOUNT
class CustomerAccount(models.Model):
    CUSTOMER_ACCOUNT_TYPES = [
        ("normal", "Normal Customer"),
        ("community", "Community Group"),
        ("restaurant", "Restaurant"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True)
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True)

    account_type = models.CharField(max_length=20, choices=CUSTOMER_ACCOUNT_TYPES)
    accepted_terms = models.BooleanField(default=False)
    account_verified = models.BooleanField(default=False)


    class Meta:
        db_table = "customer_account"

    def __str__(self):
        return f"{self.user.email} ({self.account_type})"



# CUSTOMER - COMMUNITY GROUP

class CommunityGroup(models.Model):
    ORG_STATUS_CHOICES = [
        ("charity", "Charity"),
        ("education", "Education"),
    ]

    customer_account = models.OneToOneField(CustomerAccount, on_delete=models.CASCADE)
    organisation_name = models.CharField(max_length=255)
    organisation_status = models.CharField(max_length=20, choices=ORG_STATUS_CHOICES)
    phone = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = "community_group"

    def __str__(self):
        return self.organisation_name


# CUSTOMER - RESTAURANT
class Restaurant(models.Model):
    customer_account = models.OneToOneField(CustomerAccount, on_delete=models.CASCADE)
    organisation_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    
    class Meta:
        db_table = "restaurant"

    def __str__(self):
        return self.organisation_name


# PRODUCER ACCOUNT
class ProducerAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    business_name = models.CharField(max_length=255)
    contact_person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True)
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True)
    account_verified = models.BooleanField(default=False)

    class Meta:
        db_table = "producer_account"

    def __str__(self):
        return f"{self.business_name} ({self.user.email})"



class DeletionAudit(models.Model):
    hashed_user_identifier = models.CharField(max_length=255)
    role = models.CharField(max_length=50)
    reason = models.TextField()
    deleted_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"DeletionAudit({self.role}, {self.deleted_at})"

    @staticmethod
    def from_user(user, reason: str):
        hashed_id = hashlib.sha256(str(user.id).encode()).hexdigest()
        return DeletionAudit.objects.create(
            hashed_user_identifier=hashed_id,
            role=user.role,
            reason=reason,
        )

# Failed login attempt
class FailedLoginAttempt(models.Model):
    email = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "failed_login_attempts"

    def __str__(self):
        return f"Failed login for {self.email} at {self.timestamp}"
