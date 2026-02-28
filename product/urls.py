from django.urls import path
from . import views


urlpatterns = [
    path('', views.home, name='home'),
    path('orders/', views.orders, name='orders'),
    path('user_accounts/', views.about_us, name='about_us'),
    path('category/<str:category_name>/', views.products_category, name="products_category"),
]
