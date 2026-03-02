from datetime import timedelta
from django.utils import timezone
from django.db.models import Count
from ..producers.models import Cart, CartItem

class CartStabilizer:

    EXPIRY_DAYS = 60

    @classmethod
    def delete_expired_items(cls):
        cutoff = timezone.now() - timedelta(days=cls.EXPIRY_DAYS)
        CartItem.objects.filter(created_at__lt=cutoff).delete()

    @classmethod
    def delete_empty_carts(cls):
        Cart.objects.annotate(item_count=Count('cartitem')).filter(item_count=0).delete()

    @classmethod
    def run(cls):
        cls.delete_expired_items()
        cls.delete_empty_carts()