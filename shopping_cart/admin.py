from django.contrib import admin
from .models import ShoppingCart, ShoppingCartItem


class ShoppingCartItemInline(admin.TabularInline):
    model = ShoppingCartItem
    extra = 0
    readonly_fields = ('product_id', 'quantity', 'unit_price')


class ShoppingCartAdmin(admin.ModelAdmin):
    list_display = ('cart_id', 'user_id', 'cart_status', 'created_at')
    list_filter = ('cart_status', 'created_at')
    search_fields = ('user_id', 'cart_id')
    inlines = [ShoppingCartItemInline]


class ShoppingCartItemAdmin(admin.ModelAdmin):
    list_display = ('cart_item_id', 'cart_id', 'product_id', 'quantity', 'unit_price')





admin.site.register(ShoppingCart, ShoppingCartAdmin)
admin.site.register(ShoppingCartItem, ShoppingCartItemAdmin)
