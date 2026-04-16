from django.urls import path
from . import views
from . import notification_views
from .views import ProducerCreateProductAPI, ProducerDashboardAPI, ProducerOrdersAPI, ProducerProductListAPI, ProducerDeleteProductAPI, ProducerUpdateOrderStatusAPI, ProducerUpdateProductAPI, ProducerWeeklyPaymentsAPI
app_name = "producers"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("api/dashboard/", ProducerDashboardAPI.as_view(), name="dashboard_api"),
    path("product_management/", views.product_management, name="product_management"),
    path("product_management/add/", views.add_product, name="add_product"),
    path("api/products/create/", ProducerCreateProductAPI.as_view(), name="api_create_product"),
    path("api/products/", ProducerProductListAPI.as_view(), name="api_list_products"),
    path("api/products/<int:product_id>/delete/", ProducerDeleteProductAPI.as_view(), name="api_delete_product"),
    path("api/products/<int:product_id>/update/",views.ProducerUpdateProductAPI.as_view(), name="api_update_product"),

    path("order_management/", views.order_management, name="order_management"),
    path("api/orders/", ProducerOrdersAPI.as_view(), name="producer_orders_api"),
    path("api/orders/<int:order_id>/status/",ProducerUpdateOrderStatusAPI.as_view(),),
    path("payments/", views.payments, name="payments"),
    path("api/weekly-payments/",views.ProducerWeeklyPaymentsAPI.as_view(),name="producer_weekly_payments"),
    path('api/weekly-payments/weeks/', views.ProducerWeeklyPaymentsWeeksAPI.as_view(), name='weekly_payments_weeks'),
    path('api/weekly-payments/history/', views.ProducerWeeklyPaymentsHistoryAPI.as_view(), name='weekly_payments_history'),
    path("api/weekly-payments/report/", views.ProducerWeeklyPaymentsCSV.as_view(), name="weekly_payments_csv"),
    path("api/weekly-payments/process/", views.ProcessSettlementAPI.as_view(), name="process_settlement"),

    # Producer Notifications
    path('notifications/', notification_views.producer_notifications_page, name='producer_notifications'),
    path('notifications/api/list/', notification_views.get_producer_notifications, name='api_producer_notifications'),
    path('notifications/api/read/<int:notification_id>/', notification_views.mark_producer_notification_read, name='api_producer_notification_read'),
    path('notifications/api/read-all/', notification_views.mark_all_producer_read, name='api_producer_notifications_read_all'),
    path('notifications/api/unread-count/', notification_views.get_producer_unread_count, name='api_producer_unread_count'),
    path('api/low-stock-alerts/', views.get_low_stock_alerts, name='low_stock_alerts'),
    path('api/low-stock-alerts/<int:alert_id>/resolve/', views.resolve_low_stock_alert, name='resolve_low_stock_alert'),
    path("api/products/<int:product_id>/surplus/create/", views.ProducerCreateSurplusDealAPI.as_view(), name="api_create_surplus"),
    path("api/surplus/", views.ProducerSurplusDealsAPI.as_view(), name="api_list_surplus"),
    path("api/surplus/<int:surplus_id>/remove/", views.ProducerRemoveSurplusDealAPI.as_view(), name="api_remove_surplus"),
]
