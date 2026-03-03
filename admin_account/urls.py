from django.urls import path
from .views import (
    AdminHomePageView,
    PendingAccountsView,
    ApproveAccountView,
    RejectAccountView
)

urlpatterns = [
    path("home/", AdminHomePageView.as_view(), name="admin_home"),
    path("pending/", PendingAccountsView.as_view(), name="admin_pending"),
    path("approve/", ApproveAccountView.as_view(), name="admin_approve"),
    path("reject/", RejectAccountView.as_view(), name="admin_reject"),
]