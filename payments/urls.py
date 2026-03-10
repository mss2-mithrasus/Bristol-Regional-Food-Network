from django.urls import path
from . import views
app_name = 'payments'

urlpatterns = [
    path('create-payment-intent/', views.create_payment_intent, name='create_payment_intent'),
    path('pay/', views.payment_page, name='payment_page'),
    path('success/', views.payment_success, name='payment_success'),
    path('pay/success/', views.payment_success, name='payment_success_alt'),
]