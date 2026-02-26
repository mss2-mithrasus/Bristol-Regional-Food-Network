from django.urls import path
from . import views

app_name = "producers"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("product_management/", views.product_management, name="product_management"),
    path("product_management/add/", views.add_product, name="add_product"),
]