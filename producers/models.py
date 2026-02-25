from django.db import models
from user_accounts.models import User
import uuid

class ProducerAccount(models.Model):
    """Producer account model for farmers and food producers"""
    
    producer = models.OneToOneField(User, on_delete=models.CASCADE, 
                                    primary_key=True, related_name='producer_profile')
    
    # Business information
    business_name = models.CharField(max_length=200)
    business_address = models.TextField()
    business_postcode = models.CharField(max_length=10)
    business_phone = models.CharField(max_length=20)
    business_email = models.EmailField()
    
    # Farm/Producer details
    farm_description = models.TextField(blank=True)
    farm_logo = models.ImageField(upload_to='producer_logos/', null=True, blank=True)
    cover_image = models.ImageField(upload_to='producer_covers/', null=True, blank=True)
    
    # Location for food miles calculation
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Certification information
    organic_certified = models.BooleanField(default=False)
    organic_certification_body = models.CharField(max_length=100, blank=True)
    organic_certificate = models.FileField(upload_to='certificates/', null=True, blank=True)
    
    # Delivery settings
    default_lead_time_hours = models.IntegerField(default=48, 
                                                   help_text="Default lead time in hours (minimum 48)")
    delivery_radius_miles = models.IntegerField(default=20, 
                                                help_text="Maximum delivery distance in miles")
    
    # Payment settings
    payout_account_holder = models.CharField(max_length=200, blank=True)
    payout_sort_code = models.CharField(max_length=8, blank=True)
    payout_account_number = models.CharField(max_length=8, blank=True)
    payout_bank_name = models.CharField(max_length=100, blank=True)
    
    # Business hours for pickup/delivery
    business_hours = models.JSONField(default=dict, blank=True,
                                      help_text="JSON field for business hours")
    
    # Status
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    joined_date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "producer_accounts"
        ordering = ['business_name']
    
    def __str__(self):
        return f"{self.business_name} ({'Verified' if self.is_verified else 'Unverified'})"
    
    def save(self, *args, **kwargs):
        # Ensure lead time is at least 48 hours
        if self.default_lead_time_hours < 48:
            self.default_lead_time_hours = 48
        super().save(*args, **kwargs)
    
    def get_payment_display(self):
        """Return masked payment details for display"""
        if self.payout_account_number and len(self.payout_account_number) >= 4:
            return f"****{self.payout_account_number[-4:]}"
        return "Not set"


class ProducerProductCategory(models.Model):
    """Categories that a producer specializes in"""
    
    producer = models.ForeignKey(ProducerAccount, on_delete=models.CASCADE, 
                                 related_name='specializations')
    category_name = models.CharField(max_length=100)
    
    class Meta:
        db_table = "producer_categories"
        unique_together = ['producer', 'category_name']
    
    def __str__(self):
        return f"{self.producer.business_name} - {self.category_name}"


class ProducerDeliveryPostcode(models.Model):
    """Specific postcodes that a producer delivers to"""
    
    producer = models.ForeignKey(ProducerAccount, on_delete=models.CASCADE,
                                 related_name='delivery_postcodes')
    postcode = models.CharField(max_length=10)
    delivery_fee = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    minimum_order = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    
    class Meta:
        db_table = "producer_delivery_postcodes"
        unique_together = ['producer', 'postcode']
    
    def __str__(self):
        return f"{self.producer.business_name} delivers to {self.postcode}"