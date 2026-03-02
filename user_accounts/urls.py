from django.urls import path
from django.shortcuts import render
from .views import (
    home_page, registration_page, login_page, about_page, terms_and_conditions_page,
    RegisterView, LoginView, LogoutView,
    ProducerOnlyView, CustomerOnlyView, AdminOnlyView, DeleteAccountView, RequestDeletionView
)

urlpatterns = [
    path("", home_page, name="home"),
    path("login/", login_page, name="login"),
    path("register/", registration_page, name="register"),
    path("about/", about_page, name="about"),
    path("terms_and_conditions/", terms_and_conditions_page, name="tc"),

<<<<<<< HEAD
    path("customer/home/", lambda r: render(r, "customer_home_page.html")),
    path("producer/home/", lambda r: render(r, "dashboard.html")),
=======
    path("customer/home/", lambda r: render(r, "product.html")),
    path("producer/home/", lambda r: render(r, "producer_home_page.html")),
>>>>>>> origin/main
    path("admin/home/", lambda r: render(r, "admin_home_page.html")),

    path("api/register/", RegisterView.as_view(), name="api-register"),
    path("api/login/", LoginView.as_view(), name="api-login"),
    path("api/logout/", LogoutView.as_view(), name="api-logout"),

    path("api/producer-only/", ProducerOnlyView.as_view(), name="producer-only"),
    path("api/customer-only/", CustomerOnlyView.as_view(), name="customer-only"),
    path("api/admin-only/", AdminOnlyView.as_view(), name="admin-only"),

    path("api/delete-account/", DeleteAccountView.as_view(), name="delete-account"),
    path("api/request-deletion/", RequestDeletionView.as_view(), name="request-deletion"),

]