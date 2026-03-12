from django.urls import path
from .views import (
    AdminHomePageView,
    PendingAccountsView,
    ApproveAccountView,
    RejectAccountView,
    # ADDED (10-03-26)
    DeletedAccountsView,
    FailedLoginAttemptsView
)

urlpatterns = [
    path("home/", AdminHomePageView.as_view(), name="admin_home"),
    path("pending/", PendingAccountsView.as_view(), name="admin_pending"),
    path("approve/", ApproveAccountView.as_view(), name="admin_approve"),
    path("reject/", RejectAccountView.as_view(), name="admin_reject"),
    # ADDED (10-03-26)
    path("deleted-accounts/", DeletedAccountsView.as_view(), name="admin_deleted_accounts"),
    path("failed-logins/", FailedLoginAttemptsView.as_view(), name="admin_failed_logins"),

]