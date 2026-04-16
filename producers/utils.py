from decimal import Decimal
from django.utils import timezone
from .models import SurplusDiscount
from product.models import Product
from datetime import timedelta

# Gets the earliest fullfilment date based on the 48hrs lead time 
def get_earliest_fulfilment_date():
    return timezone.now().date() + timedelta(days=2)
# Checks if product is valid for fulfilment 
def is_product_valid_for_fulfilment(product):
    earliest_fulfilment_date = get_earliest_fulfilment_date()

    if product.stock_quantity <= 0:
        return False

    if product.is_expired:
        return False

    if product.best_before_date and product.best_before_date < earliest_fulfilment_date:
        return False

    return True
# Surplus Discount 
def expire_surplus_deals():
    """
    Mark any active surplus deals as expired once the expiry date has passed.
    """
    expired_count = SurplusDiscount.objects.filter(
        status="active",
        expiry_date__lte=timezone.now()
    ).update(status="expired")

    return expired_count


def get_active_surplus_deal(product):
    """
    Return the current active surplus deal for a product, if any.
    """
    expire_surplus_deals()

    if not is_product_valid_for_fulfilment(product):
        return None

    return (
        SurplusDiscount.objects
        .filter(
            product=product,
            status="active",
            expiry_date__gt=timezone.now(),
        )
        .order_by("-date_discount_created")
        .first()
    )


def get_effective_product_price(product):
    """
    Return the discounted price if the product has an active surplus deal.
    Otherwise return the normal product price.
    """
    deal = get_active_surplus_deal(product)

    if not deal:
        return product.price

    multiplier = Decimal("1.00") - (Decimal(deal.discount_percentage) / Decimal("100"))
    return (product.price * multiplier).quantize(Decimal("0.01"))

def deactivate_surplus_if_sold_out(product):
    """
    Cancel any active surplus deal if the product has sold out.
    """
    if product.stock_quantity <= 0:
        SurplusDiscount.objects.filter(
            product=product,
            status="active"
        ).update(status="cancelled")


def deactivate_expired_products():
    """
    Mark products as expired once their best before date has passed.
    Also expire any active surplus deals linked to those products.
    """
    today = timezone.now().date()

    expired_products = Product.objects.filter(
        best_before_date__isnull=False,
        best_before_date__lt=today,
        availability_status=True
    )

    count = 0

    for product in expired_products:
        product.availability_status = False
        product.is_expired = True
        product.save(update_fields=["availability_status", "is_expired"])

        SurplusDiscount.objects.filter(
            product=product,
            status="active"
        ).update(status="expired")

        count += 1

    return count

def deactivate_surplus_if_not_fulfillable(product):
    """
    Cancel any active surplus deal if the product can no longer be fulfilled.
    """
    if not is_product_valid_for_fulfilment(product):
        SurplusDiscount.objects.filter(
            product=product,
            status="active"
        ).update(status="cancelled")