from django.urls import path
from django.shortcuts import render
from .views import (
    home_page, registration_page, login_page, about_page, terms_and_conditions_page, user_profile_page,
    RegisterView, LoginView, LogoutView,
    ProducerOnlyView, CustomerOnlyView, AdminOnlyView, UserProfileView, UpdateUserProfileView,
    SoftDeleteAccountView, HardDeleteAccountView, failed_login_attempts_view, deleted_accounts_view
)
from admin_account.views import (
    AdminHomePageView,
    PendingAccountsView,
    ApproveAccountView,
    RejectAccountView
)

urlpatterns = [
    path("", home_page, name="home"),
    path("login/", login_page, name="login"),
    path("register/", registration_page, name="register"),
    path("about/", about_page, name="about"),
    path("terms_and_conditions/", terms_and_conditions_page, name="tc"),
    path("user_profile/", user_profile_page, name="user_profile"),
    
    path("customer/home/", lambda r: render(r, "product.html")),
    path("producer/home/", lambda r: render(r, "producer_home_page.html")),
    
    path("api/register/", RegisterView.as_view(), name="api-register"),
    path("api/login/", LoginView.as_view(), name="api-login"),
    path("api/logout/", LogoutView.as_view(), name="api-logout"),
    path("api/user/profile/", UserProfileView.as_view(), name="user-profile"),
    path("api/user/update/", UpdateUserProfileView.as_view(), name="user-update"),    
    path("api/producer-only/", ProducerOnlyView.as_view(), name="producer-only"),
    path("api/customer-only/", CustomerOnlyView.as_view(), name="customer-only"),
    path("api/admin-only/", AdminOnlyView.as_view(), name="admin-only"),

    path("api/account/soft-delete/", SoftDeleteAccountView.as_view(), name="soft-delete"),
    path("api/account/hard-delete/", HardDeleteAccountView.as_view(), name="hard-delete"),

    path("failed-logins/", failed_login_attempts_view, name="failed_logins"),
    path("deleted-accounts/", deleted_accounts_view, name="deleted_accounts"),

]