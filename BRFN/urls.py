from django.contrib import admin
from django.urls import path, include
from user_accounts.views import home_page, registration_page, login_page
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView

urlpatterns = [
    path('customer/home/', include("product.urls")),
    path("", include("user_accounts.urls")),
    path("producer/", include("producers.urls")),
    path("admin-dashboard/", include("admin_account.urls")),
    path('cart/', include('shopping_cart.urls')), 
    path('admin/', admin.site.urls),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'), 
    path("orders/", include("order_management.urls")), 
    path("notifications/", include('notifications.urls')),
    path('api/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),  
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
