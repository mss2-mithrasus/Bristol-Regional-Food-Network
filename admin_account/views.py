from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.views import View

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser

from user_accounts.models import (
    CustomerAccount,
    ProducerAccount,
    User
)

# Check if user is admin
def is_admin(user):
    return user.is_authenticated and user.role == "admin"


# Admin home page 
@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin), name="dispatch")
class AdminHomePageView(View):
    def get(self, request):
        pending_customers = CustomerAccount.objects.filter(account_verified=False)
        pending_producers = ProducerAccount.objects.filter(account_verified=False)

        return render(request, "admin_home_page.html", {
            "pending_customers": pending_customers,
            "pending_producers": pending_producers,
        })


# Show pending accounts
class PendingAccountsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        customers = CustomerAccount.objects.filter(account_verified=False)
        producers = ProducerAccount.objects.filter(account_verified=False)

        return Response({
            "customers": [
                {
                    "user_id": c.user.id,
                    "email": c.user.email,
                    "account_type": c.account_type
                }
                for c in customers
            ],
            "producers": [
                {
                    "user_id": p.user.id,
                    "email": p.user.email,
                    "business_name": p.business_name
                }
                for p in producers
            ]
        })


# Approve account
class ApproveAccountView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        user_id = request.data.get("user_id")
        role = request.data.get("role")

        if role == "producer":
            ProducerAccount.objects.filter(user_id=user_id).update(account_verified=True)
        else:
            CustomerAccount.objects.filter(user_id=user_id).update(account_verified=True)

        return Response({"message": "Account approved"})


# Reject account
class RejectAccountView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        user_id = request.data.get("user_id")
        User.objects.filter(id=user_id).delete()
        return Response({"message": "Account rejected"})