from django.urls import path
from . import views



urlpatterns = [
    path('', views.home, name='home'),
    path('customer/home/', views.home, name='customer-home'),
    path('orders/', views.orders, name='orders'),
    path('user_accounts/', views.about_us, name='about_us'),
    
    
    path('api/categories/', views.ProductCategoryCreateAPIView.as_view(), name='api-categories-create'),
    path('api/categories/list/', views.ProductCategoryListAPIView.as_view(), name='api-categories-list'),
    path('api/products/create/', views.ProductCreateAPIView.as_view(), name="api-product-create"),
    path('api/products/allergen/', views.ProductAllergenCreateAPIView.as_view(), name='api-product-allergen'),
    path('category/<str:category_name>/', views.products_category, name="products_category"),
    path('product/<int:product_id>', views.product_detail, name="product_detail"),
    
]
