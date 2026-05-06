# notifications/seasonal_notify.py
from django.utils import timezone
from datetime import timedelta
from product.models import Product, SeasonalAvailability
from user_accounts.models import ProducerAccount
from .models import ProducerNotification

def notify_producers_upcoming_seasonal_products(days_before=7):
    """
    Send notifications to producers when their seasonal products will be available in X days.
    Called by management command (cron job).
    """
    today = timezone.now().date()
    upcoming_date = today + timedelta(days=days_before)

    upcoming_seasonal = SeasonalAvailability.objects.filter(
        is_year_round=False,
        season_start_date=upcoming_date
    ).select_related('product', 'product__producer')

    notifications_created = 0

    for season in upcoming_seasonal:
        product = season.product
        producer = product.producer
        producer_user = producer.user

        if not product or not producer or not producer_user:
            continue

        notifications_created += _send_seasonal_notification(product, producer_user, upcoming_date)

    return notifications_created


def notify_single_product_seasonal(product):
    """
    Check a single product and notify its producer if the season starts within 7 days.
    Called when a product is created or updated with season dates.
    """
    season = product.seasonal_availability.first()
    if not season or season.is_year_round or not season.season_start_date:
        return 0

    today = timezone.now().date()
    days_until_start = (season.season_start_date - today).days

    if not (0 <= days_until_start <= 7):
        return 0

    producer = product.producer
    if not producer or not producer.user:
        return 0

    upcoming_date = season.season_start_date
    return _send_seasonal_notification(product, producer.user, upcoming_date)


def _send_seasonal_notification(product, producer_user, upcoming_date):
    today = timezone.now().date()

    # Only block if we already notified about this exact start date
    existing = ProducerNotification.objects.filter(
        recipient=producer_user,
        notification_type='seasonal_coming_soon',
        product=product,
        title__icontains=upcoming_date.strftime("%d %b %Y")  # checks the specific date
    ).exists()

    if existing:
        return 0

    ProducerNotification.objects.create(
        recipient=producer_user,
        notification_type='seasonal_coming_soon',
        title=f'Seasonal Product Coming Soon: {product.name}',
        message=(
            f'Your product "{product.name}" will become available on '
            f'{upcoming_date.strftime("%d %b %Y")}. '
            f'Current stock: {product.stock_quantity}. '
            f'Make sure you have enough inventory!'
        ),
        product=product,
        is_read=False,
        is_seen=False
    )

    print(f"Sent seasonal notification to {producer_user.email} for {product.name}")
    return 1