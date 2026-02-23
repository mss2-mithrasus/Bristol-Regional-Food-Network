"""
URL configuration for BRFN project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from producers.views import db_test,home
from user_accounts.views import accounts_test
from notifications.views import notifications_test
from customer_reviews.views import reviews_test


urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('db-test/', db_test),
    path('accounts-test/', accounts_test),
    path('notifications-test/', notifications_test),
    path('reviews-test/', reviews_test),
]
