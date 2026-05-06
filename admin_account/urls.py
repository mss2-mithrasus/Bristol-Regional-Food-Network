from django.urls import path
from .views import (
    AdminHomePageView,
    PendingAccountsView,
    ApproveAccountView,
    RejectAccountView,
    DeletedAccountsView,
    FailedLoginAttemptsView,
    AdminPendingPageView,
    AdminFailedLoginsPageView,
    AdminDeletedAccountsPageView,
    AdminFinancialReportsPageView,
    AdminAnalyticsPageView,
    PendingReviewsView,
    ApproveReviewView,
    RejectReviewView,
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

    
    path("approve/", ApproveAccountView.as_view(), name="admin_approve_account"),
    path("reject/", RejectAccountView.as_view(), name="admin_reject_account"),
    
    
    
    path("reviews/pending/", PendingReviewsView.as_view(), name="pending_reviews"),
    path("reviews/<int:review_id>/approve/", ApproveReviewView.as_view(), name="approve_review"),
    path("reviews/<int:review_id>/reject/", RejectReviewView.as_view(), name="reject_review"),


]