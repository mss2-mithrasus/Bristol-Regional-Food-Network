from django.urls import path
from . import views

urlpatterns = [
    # Page view
    path('', views.notifications_page, name='notifications'),
    
    # API endpoints
    path('api/list/', views.get_notifications, name='api_notifications'),
    path('api/read/<int:notification_id>/', views.mark_notification_read, name='api_notification_read'),
    path('api/read-all/', views.mark_all_read, name='api_notifications_read_all'),
    path('api/unread-count/', views.get_unread_count, name='api_unread_count'),
    
    # Stock alerts
    path('api/alerts/', views.get_stock_alerts, name='api_stock_alerts'),
    path('api/alerts/create/', views.create_stock_alert, name='api_create_alert'),
    path('api/alerts/<int:alert_id>/', views.delete_stock_alert, name='api_delete_alert'),
]