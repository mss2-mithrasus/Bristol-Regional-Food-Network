from rest_framework import serializers
from .models import Notification, StockAlert
from product.serializers import ProductSerializer

class NotificationSerializer(serializers.ModelSerializer):
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'notification_id',
            'notification_type',
            'title',
            'message',
            'is_read',
            'is_seen',
            'created_at',
            'time_ago',
        ]
    
    def get_time_ago(self, obj):
        from django.utils import timezone
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"


class StockAlertSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    
    class Meta:
        model = StockAlert
        fields = [
            'alert_id',
            'product',
            'product_details',
            'requested_quantity',
            'created_at',
            'is_active',
            'notified_at',
        ]
        read_only_fields = ['alert_id', 'created_at', 'notified_at']


class CreateStockAlertSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=99)