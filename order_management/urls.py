from django.urls import path
from . import views

urlpatterns = [
    path('checkout/', views.checkout_view, name='checkout'),
    path('orders/', views.order_history_view, name='order_history'),
    path('confirmation/<str:order_number>/', views.order_confirmation_view, name='order_confirmation'),
]