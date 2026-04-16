from django.urls import path
from . import views



urlpatterns = [
    path('surplus-deals/', views.surplus_deals_page, name='surplus-deals-page'),
    path('api/surplus-deals/', views.SurplusDealsAPIView.as_view(), name='api-surplus-deals'),
    path('category/<str:category_name>/', views.category_page, name='category-page'),
    path('api/customer/', views.CustomerAPIView.as_view(), name='api-customer'),
    path('api/categories/', views.ProductCategoryCreateAPIView.as_view(), name='api-categories-create'),
    path('api/categories/list/', views.ProductCategoryListAPIView.as_view(), name='api-categories-list'),
    path('api/category/<str:category_name>/products/', views.CategoryProductsAPIView.as_view(), name="api-products-category"),
    path('api/products/', views.ProductSearchAPIView.as_view(), name='api.product-search'),
    path('product/<int:product_id>/', views.product_detail, name='product-detail'),
    path('api/product/<int:product_id>/', views.ProductDetailAPIView.as_view(), name="api-product_detail"),
    path('api/product/<int:product_id>/threshold/', views.update_low_stock_threshold, name='update_low_stock_threshold'),
]