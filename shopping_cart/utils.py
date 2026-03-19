# shopping_cart/utils.py
from django.utils import timezone
from django.db.models import Sum
from .models import CartItem

def get_available_stock(product, exclude_user=None):
    """
    Calculate how many units of a product are actually available for purchase
    = total stock - items reserved in active carts (excluding current user's own cart)
    """
    # Current time
    now = timezone.now()
    
    # Base queryset for active reservations
    reservations = CartItem.objects.filter(
        product=product,
        reserved_until__gt=now
    )
    
    # Exclude current user's own cart if provided
    if exclude_user and exclude_user.is_authenticated:
        reservations = reservations.exclude(cart__customer=exclude_user)
    
    # Sum up quantities
    reserved_quantity = reservations.aggregate(total=Sum('quantity'))['total'] or 0
    
    # Available = total stock - reserved by others
    available = product.stock_quantity - reserved_quantity
    
    return max(available, 0)