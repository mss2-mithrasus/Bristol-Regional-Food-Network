from django.urls import path
from .views import payments_test

urlpatterns = [
    path('payments-test/', payments_test),
]