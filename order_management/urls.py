from django.urls import path
from . import views

urlpatterns = [
    path("", views.order_home, name="orders_home"),
    path("checkout/multi/", views.multi_checkout, name="multi_checkout"),
    path('history/', views.order_history, name='order_history'),
    path('detail/<int:order_id>/', views.order_detail, name='order_detail'),
    path('reorder/<int:order_id>/', views.reorder, name='reorder'),
    # path('download-receipt/<int:order_id>/', views.download_receipt, name='download_receipt'),
    path('update-checkout-address/', views.update_checkout_address, name='update_checkout_address'), 
    # Recurring order management URLs
    path('recurring/', views.recurring_list, name='recurring_list'),
    path('recurring/<int:template_id>/', views.recurring_detail, name='recurring_detail'),
    path('recurring/<int:template_id>/toggle/', views.toggle_recurring, name='toggle_recurring'),
    path('recurring/instance/<int:instance_id>/edit/', views.edit_upcoming_order, name='edit_upcoming_order'), # This line
]