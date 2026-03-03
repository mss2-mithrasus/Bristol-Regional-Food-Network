from django.urls import path
from . import views

app_name = "shopping_cart"  # <--- THIS IS THE NAMESPACE

urlpatterns = [
    path("", views.cart_page, name="cart_page"),
    path("cart/add/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/update/<int:item_id>/", views.update_quantity, name="update_quantity"),
    path("cart/remove/<int:item_id>/", views.remove_item, name="remove_item"),
]