import hashlib 
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.views import View
from user_accounts.permissions import IsAdmin

from rest_framework.views import APIView
from rest_framework.response import Response

from user_accounts.models import (
    CustomerAccount,
    ProducerAccount,
    User,
    DeletionAudit,
    FailedLoginAttempt
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
    permission_classes = [IsAdmin]

    def get(self, request):
        customers = CustomerAccount.objects.filter(account_verified=False).select_related(
            "user", "person"
        ).prefetch_related("communitygroup", "restaurant")
        producers = ProducerAccount.objects.filter(account_verified=False).select_related(
            "user", "contact_person"
        )

        customer_list = []

        for c in customers:
            base = {
                "user_id": c.user.id,
                "email": c.user.email,
                "account_type": c.account_type,
            }

            if c.account_type == "normal":
                person = c.person
                base.update({
                    "name": f"{person.first_name} {person.last_name}" if person else "N/A",
                    "phone": person.phone if person else None,
                    "organisation_name": None,
                })

            elif c.account_type == "community":
                cg = getattr(c, "communitygroup", None)
                base.update({
                    "name": cg.organisation_name if cg else "N/A",
                    "organisation_name": cg.organisation_name if cg else None,
                    "phone": cg.phone if cg else None,
                })

            elif c.account_type == "restaurant":
                r = getattr(c, "restaurant", None)
                base.update({
                    "name": r.organisation_name if r else "N/A",
                    "organisation_name": r.organisation_name if r else None,
                    "phone": r.phone if r else None,
                })

            customer_list.append(base)

        producer_list = []
        for p in producers:
            person = p.contact_person
            producer_list.append({
                "user_id": p.user.id,
                "email": p.user.email,
                "business_name": p.business_name,
                "name": f"{person.first_name} {person.last_name}" if person else "N/A",
                "phone": person.phone if person else None,
            })

        return Response({
            "customers": customer_list,
            "producers": producer_list
        })
# Approve account
class ApproveAccountView(APIView):
    permission_classes = [IsAdmin]

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
    permission_classes = [IsAdmin]

    def post(self, request):
        user_id = request.data.get("user_id")
        User.objects.filter(id=user_id).delete()
        return Response({"message": "Account rejected"})

# ADDED (10-03-26)
# Deleted account history
class DeletedAccountsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        audits = DeletionAudit.objects.all().order_by("-deleted_at")

        results = []
        for entry in audits:
            results.append({
                "hashed_user_identifier": entry.hashed_user_identifier,
                "role": entry.role,
                "reason": entry.reason,
                "deleted_at": entry.deleted_at,
            })

        return Response(results)
    
# Failed login attempts history
class FailedLoginAttemptsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        attempts = FailedLoginAttempt.objects.all().order_by("-timestamp")

        results = []
        for attempt in attempts:
            results.append({
                "email": attempt.email,
                "ip_address": attempt.ip_address,
                "user_agent": attempt.user_agent,
                "timestamp": attempt.timestamp,
            })

        return Response(results)
