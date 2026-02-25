from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid

class User(AbstractUser):
    """Base user model extending Django's AbstractUser"""
    
    USER_TYPES = [
        ('customer', 'Customer'),
        ('producer', 'Producer'),
        ('admin', 'Administrator'),
    ]
    
    user_id = models.AutoField(primary_key=True)
    email = models.EmailField(unique=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='customer')
    
    # Personal information
    phone = models.CharField(max_length=20, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
        # ✅ FIX: Add related_name to avoid clashes with auth.User
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name="custom_user_set",  # ✅ Add this
        related_query_name="custom_user",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name="custom_user_set",  # ✅ Add this
        related_query_name="custom_user",
    )

    # Override username field to use email for login
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # username is still required by AbstractUser
    
    class Meta:
        db_table = "users"
    
    def __str__(self):
        return f"{self.email} ({self.user_type})"


class CustomerAccount(models.Model):
    """Extended profile for customer users"""
    
    customer = models.OneToOneField(User, on_delete=models.CASCADE, 
                                    primary_key=True, related_name='customer_profile')
    
    # Customer-specific fields
    default_delivery_address = models.TextField()
    default_postcode = models.CharField(max_length=10)
    
    # Preferences
    marketing_consent = models.BooleanField(default=False)
    
    # For community groups/organizations
    is_community_group = models.BooleanField(default=False)
    organization_name = models.CharField(max_length=200, blank=True)
    organization_type = models.CharField(max_length=50, blank=True, 
                                         choices=[
                                             ('school', 'School'),
                                             ('charity', 'Charity'),
                                             ('community', 'Community Group'),
                                             ('other', 'Other')
                                         ])
    
    # For restaurants
    is_restaurant = models.BooleanField(default=False)
    restaurant_name = models.CharField(max_length=200, blank=True)
    vat_number = models.CharField(max_length=20, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "customer_accounts"
    
    def __str__(self):
        if self.is_community_group and self.organization_name:
            return f"Community: {self.organization_name}"
        elif self.is_restaurant and self.restaurant_name:
            return f"Restaurant: {self.restaurant_name}"
        return f"Customer: {self.customer.email}"
    
    def get_delivery_address(self):
        """Return the delivery address to use for orders"""
        return self.default_delivery_address
    
    def get_postcode(self):
        """Return the postcode to use for orders"""
        return self.default_postcode