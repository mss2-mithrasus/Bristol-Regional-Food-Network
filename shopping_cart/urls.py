from django.urls import path
from . import views

urlpatterns = [
    # Page views
    path('', views.cart_view, name='cart_view'),
    
    # API endpoints
    path('api/add/', views.add_to_cart, name='api_add_to_cart'),
    path('api/item/<int:item_id>/', views.update_cart_item, name='api_update_cart_item'),
    path('api/data/', views.get_cart_data, name='api_cart_data'),
    path('api/icon/', views.cart_icon_data, name='api_cart_icon'),
    path('api/item-stock/<int:item_id>/', views.get_cart_item_available_stock, name='api_cart_item_stock'),
    path('api/check-availability/<int:product_id>/', views.check_product_availability, name='api_check_availability'),
    
]