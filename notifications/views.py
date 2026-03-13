from django.shortcuts import render

# Create your views here.
from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from .models import Notification, StockAlert
from product.models import Product
from .serializers import NotificationSerializer, StockAlertSerializer, CreateStockAlertSerializer


def notifications_page(request):
    """Render the notifications page"""
    return render(request, 'notifications.html')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    """Get all notifications for the current user"""
    notifications = Notification.objects.filter(recipient=request.user)
    
    # Mark as seen when fetched
    # notifications.filter(is_seen=False).update(is_seen=True)
    
    serializer = NotificationSerializer(notifications, many=True)
    
    unread_count = Notification.objects.filter(
        recipient=request.user, 
        is_read=False
    ).count()
    
    return Response({
        'notifications': serializer.data,
        'unread_count': unread_count
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    try:
        notification = Notification.objects.get(
            notification_id=notification_id,
            recipient=request.user
        )
        notification.is_read = True
        notification.save()
        
        return Response({'success': True})
    except Notification.DoesNotExist:
        return Response({'error': 'Notification not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).update(is_read=True)
    
    return Response({'success': True})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_unread_count(request):
    """Get unread notification count"""
    count = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    return Response({'unread_count': count})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def create_stock_alert(request):
    """Create a stock alert for a product"""
    serializer = CreateStockAlertSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    
    product_id = serializer.validated_data['product_id']
    quantity = serializer.validated_data['quantity']
    
    try:
        product = Product.objects.get(product_id=product_id)
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=404)
    
    # Check if alert already exists
    alert, created = StockAlert.objects.get_or_create(
        customer=request.user,
        product=product,
        defaults={
            'requested_quantity': quantity,
            'is_active': True
        }
    )
    
    if not created:
        # Update existing alert
        alert.requested_quantity = quantity
        alert.is_active = True
        alert.notified_at = None
        alert.save()
    
    return Response({
        'success': True,
        'message': f'You will be notified when {product.name} is available'
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_stock_alert(request, alert_id):
    """Delete a stock alert"""
    try:
        alert = StockAlert.objects.get(
            alert_id=alert_id,
            customer=request.user
        )
        alert.delete()
        return Response({'success': True})
    except StockAlert.DoesNotExist:
        return Response({'error': 'Alert not found'}, status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_stock_alerts(request):
    """Get all stock alerts for the current user"""
    alerts = StockAlert.objects.filter(
        customer=request.user,
        is_active=True
    ).select_related('product')
    
    serializer = StockAlertSerializer(alerts, many=True)
    return Response(serializer.data)