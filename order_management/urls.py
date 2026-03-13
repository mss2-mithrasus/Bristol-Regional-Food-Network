from django.urls import path
from . import views

urlpatterns = [
    path("", views.order_home, name="orders_home"),

    path("checkout/multi/", views.multi_checkout, name="multi_checkout"),
    path('history/', views.order_history, name='order_history'),
    path('detail/<int:order_id>/', views.order_detail, name='order_detail'),
    path('update-checkout-address/', views.update_checkout_address, name='update_checkout_address'),
    #path("payment/", views.payment, name="payment_page"),

]