from django.urls import path
from . import views

urlpatterns = [
    path("", views.order_home, name="orders_home"),

    path("checkout/multi/", views.multi_checkout, name="multi_checkout"),
    path("payment/", views.payment, name="payment_page"),

]