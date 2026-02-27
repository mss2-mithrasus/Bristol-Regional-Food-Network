from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),

    # Products page
    path("products/", views.products_page, name="products_page"),

    # Cart page
    path("cart/", views.cart_page, name="cart_page"),

    # Add to cart
    path("add/<int:product_id>/", views.add_to_cart, name="add_to_cart"),

    # Update quantity
    path("update/<int:item_id>/", views.update_quantity, name="update_quantity"),

    # Remove item
    path("remove/<int:item_id>/", views.remove_item, name="remove_item"),
]