from django.contrib import admin

from django.contrib import admin
from .models import (
    User, Person, Address,
    CustomerAccount, CommunityGroup, Restaurant,
    ProducerAccount
)


# User admin
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "role", "is_active", "date_created")
    list_filter = ("role", "is_active")
    search_fields = ("email",)


# Customer account admin
@admin.register(CustomerAccount)
class CustomerAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "account_type", "account_verified")
    list_filter = ("account_type", "account_verified")
    search_fields = ("user__email",)

    actions = ["verify_accounts"]

    def verify_accounts(self, request, queryset):
        queryset.update(account_verified=True)
    verify_accounts.short_description = "Set selected customer accounts as verified"


# Community group admin
@admin.register(CommunityGroup)
class CommunityGroupAdmin(admin.ModelAdmin):
    list_display = ("organisation_name", "organisation_status", "customer_account")
    list_filter = ("organisation_status",)
    search_fields = ("organisation_name",)


# Restaurant admin
@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ("organisation_name", "customer_account")
    search_fields = ("organisation_name",)


# Producer admin
@admin.register(ProducerAccount)
class ProducerAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "business_name", "account_verified")
    list_filter = ("account_verified",)
    search_fields = ("business_name", "user__email")

    actions = ["verify_producers"]

    def verify_producers(self, request, queryset):
        queryset.update(account_verified=True)
    verify_producers.short_description = "Set selected producers as verified"
