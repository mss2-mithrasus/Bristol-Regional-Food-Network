from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from notifications.models import ProducerNotification
from notifications.serializers import NotificationSerializer

def producer_notifications_page(request):
    """Render the producer notifications page"""
    return render(request, 'producer_notifications.html')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_producer_notifications(request):
    """Get all notifications for the current producer"""
    notifications = ProducerNotification.objects.filter(recipient=request.user)
    
    serializer = NotificationSerializer(notifications, many=True)
    
    unread_count = ProducerNotification.objects.filter(
        recipient=request.user, 
        is_read=False
    ).count()
    
    return Response({
        'notifications': serializer.data,
        'unread_count': unread_count
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_producer_notification_read(request, notification_id):
    """Mark a producer notification as read"""
    try:
        notification = ProducerNotification.objects.get(
            notification_id=notification_id,
            recipient=request.user
        )
        notification.is_read = True
        notification.save()
        
        return Response({'success': True})
    except ProducerNotification.DoesNotExist:
        return Response({'error': 'Notification not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_producer_read(request):
    """Mark all producer notifications as read"""
    ProducerNotification.objects.filter(
        recipient=request.user,
        is_read=False
    ).update(is_read=True)
    
    return Response({'success': True})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_producer_unread_count(request):
    """Get unread notification count for producer"""
    count = ProducerNotification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    return Response({'unread_count': count})