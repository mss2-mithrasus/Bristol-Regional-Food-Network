from django.urls import path
from .views import (
    AdminHomePageView,
    PendingAccountsView,
    ApproveAccountView,
    RejectAccountView,
    # ADDED (10-03-26)
    DeletedAccountsView,
    FailedLoginAttemptsView,
    AdminPendingPageView,
    AdminFailedLoginsPageView,
    AdminDeletedAccountsPageView,
    AdminFinancialReportsPageView,
    AdminAnalyticsPageView,
    FinancialReportsMeta,
    FinancialReports,
    FinancialReportsCSV,
    AnalyticsData,
    AnalyticsMeta
)

urlpatterns = [
    path("home/", AdminHomePageView.as_view(), name="admin_home"),

    # NEW PAGE ROUTES
    path("pending/", AdminPendingPageView.as_view(), name="admin_pending_page"),
    path("failed-logins/", AdminFailedLoginsPageView.as_view(), name="admin_failed_page"),
    path("deleted-accounts/", AdminDeletedAccountsPageView.as_view(), name="admin_deleted_page"),
    path("financial-reports/", AdminFinancialReportsPageView.as_view(), name="admin_financial_page"),
    path("analytics/", AdminAnalyticsPageView.as_view(), name="admin_analytics_page"),

    # EXISTING API ROUTES
    path("pending/api/", PendingAccountsView.as_view(), name="admin_pending_api"),
    path("failed-logins/api/", FailedLoginAttemptsView.as_view(), name="admin_failed_api"),
    path("deleted-accounts/api/", DeletedAccountsView.as_view(), name="admin_deleted_api"),
    path("financial-reports/meta/", FinancialReportsMeta, name="admin_financial_meta"),
    path("financial-reports/api/", FinancialReports, name="admin_financial_api"),
    path("financial-reports/export-csv/", FinancialReportsCSV, name="admin_financial_csv"),
    path("analytics/meta/", AnalyticsMeta, name="admin_analytics_meta"),
    path("analytics/data/", AnalyticsData, name="admin_analytics_api"),

]