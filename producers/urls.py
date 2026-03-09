from django.urls import path
from . import views
from .views import ProducerCreateProductAPI, ProducerDashboardAPI, ProducerProductListAPI, ProducerDeleteProductAPI, ProducerUpdateProductAPI
app_name = "producers"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("api/dashboard/", ProducerDashboardAPI.as_view(), name="dashboard_api"),
    path("product_management/", views.product_management, name="product_management"),
    path("product_management/add/", views.add_product, name="add_product"),
    path("api/products/create/", ProducerCreateProductAPI.as_view(), name="api_create_product"),
    path("api/products/", ProducerProductListAPI.as_view(), name="api_list_products"),
    path("api/products/<int:product_id>/delete/", ProducerDeleteProductAPI.as_view(), name="api_delete_product"),
    path("api/products/<int:product_id>/update/",views.ProducerUpdateProductAPI.as_view(), name="api_update_product"),
    path("order_management/", views.order_management, name="order_management"),
]