from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import login
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import login
from .serializers import RegistrationSerializer, LoginSerializer, FailedLoginAttemptSerializer, DeletionAuditSerializer
from .permissions import IsProducer, IsCustomer, IsAdmin
from django.utils import timezone
from .models import User, Person, CustomerAccount, CommunityGroup, Restaurant, ProducerAccount, Address, DeletionAudit, FailedLoginAttempt
import hashlib
import logging
logger = logging.getLogger(__name__)

def home_page(request):
    return render(request, "main_home_page.html")

def registration_page(request):
    return render(request, "registration_page.html")

def login_page(request):
    return render(request, "login_page.html")

def about_page(request):
    return render(request, "about_us.html")

def terms_and_conditions_page(request):
    return render(request, "terms_and_conditions.html")

def user_profile_page(request):
    return render(request, "user_profile.html")


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({"message": "User registered successfully", "user_id": user.id}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            tokens = serializer.validated_data
            user = tokens["user"]
            
            # Create Django session
            login(request, user)
            if user.role == "admin":
                homepage = "/admin-dashboard/home/"
            elif user.role == "producer":
                homepage = "/producer/home/"
            else:
                homepage = "/customer/home/"


            return Response(
                {
                    "access": tokens["access"],
                    "refresh": tokens["refresh"],
                    "role": user.role,
                    "homepage": homepage,
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            logger.info(f"User {request.user.email} logged out from IP {request.META.get('REMOTE_ADDR')}")
            return Response({"message": "Logged out successfully"}, status=status.HTTP_200_OK)
        except Exception:
            logger.warning(f"Invalid logout attempt for token from IP {request.META.get('REMOTE_ADDR')}")
            return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)


class ProducerOnlyView(APIView):
    permission_classes = [IsProducer]

    def get(self, request):
        return Response({"message": "Producer feature accessed"}, status=status.HTTP_200_OK)


class CustomerOnlyView(APIView):
    permission_classes = [IsCustomer]

    def get(self, request):
        return Response({"message": "Customer feature accessed"}, status=status.HTTP_200_OK)


class AdminOnlyView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response({"message": "Admin access granted"}, status=status.HTTP_200_OK)



class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Person
        person = Person.objects.filter(user=user).first()

        # Customer
        customer = CustomerAccount.objects.filter(user=user).first()
        community = CommunityGroup.objects.filter(customer_account=customer).first() if customer else None
        restaurant = Restaurant.objects.filter(customer_account=customer).first() if customer else None

        # Producer
        producer = ProducerAccount.objects.filter(user=user).first()

        # Address (customer or producer)
        address = None
        if customer and customer.address:
            address = customer.address
        if producer and producer.address:
            address = producer.address

        return Response({
            "email": user.email,
            "role": user.role,

            # Person
            "first_name": person.first_name if person else "",
            "last_name": person.last_name if person else "",
            "phone": person.phone if person else "",

            # Address
            "address_line": address.address_line if address else "",
            "postcode": address.postcode if address else "",

            # Customer
            "account_type": customer.account_type if customer else "",
            "accepted_terms": customer.accepted_terms if customer else False,
            "account_verified": customer.account_verified if customer else False,

            # Community group
            "organisation_name": community.organisation_name if community else "",
            "organisation_status": community.organisation_status if community else "",
            "community_phone": community.phone if community else "",

            # Restaurant
            "restaurant_name": restaurant.organisation_name if restaurant else "",
            "restaurant_phone": restaurant.phone if restaurant else "",

            # Producer
            "business_name": producer.business_name if producer else "",
            "contact_person": (
                producer.contact_person.first_name + " " + producer.contact_person.last_name
                if producer and producer.contact_person else ""
            ),
            "producer_verified": producer.account_verified if producer else False,
        })
    
class UpdateUserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        user = request.user
        data = request.data

        # Update Person
        person = Person.objects.filter(user=user).first()
        if person:
            person.first_name = data.get("first_name", person.first_name)
            person.last_name = data.get("last_name", person.last_name)
            person.phone = data.get("phone", person.phone)
            person.save()

        # Update Address
        customer = CustomerAccount.objects.filter(user=user).first()
        producer = ProducerAccount.objects.filter(user=user).first()

        address = None
        if customer and customer.address:
            address = customer.address
        if producer and producer.address:
            address = producer.address

        if address:
            address.address_line = data.get("address_line", address.address_line)
            address.postcode = data.get("postcode", address.postcode)
            address.save()

        return Response({"message": "Profile updated successfully"})

def user_has_financial_activity(user):
    """
    Placeholder until Order, Payment, and Payout models are created.
    Always returns False so deletion is allowed.
    Replace with real logic when models are ready.
    def user_has_financial_activity(user):
    from orders.models import Order
    from payments.models import Payment
    from payouts.models import Payout

    has_pending_orders = Order.objects.filter(user=user, status__in=["pending", "processing"]).exists()
    has_unpaid_payments = Payment.objects.filter(user=user, status="unpaid").exists()

    has_pending_payouts = False
    if user.role == "producer":
        has_pending_payouts = Payout.objects.filter(producer=user, status="pending").exists()

    return has_pending_orders or has_unpaid_payments or has_pending_payouts
    """
    return False

class SoftDeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        reason = request.data.get("reason")

        if not reason:
            return Response({"error": "A reason is required."}, status=400)

        if user_has_financial_activity(user):
            return Response(
                {"error": "You cannot deactivate your account while you have pending orders, unpaid payments, or incoming payouts."},
                status=400
            )

        user.is_active = False
        user.deleted_at = timezone.now()
        user.reason_for_deleting = reason
        user.deleted_by_user = True
        user.save()

        # ADDED (10-03-26)
        # Creates audit record
        DeletionAudit.from_user(user, reason)
        return Response({"message": "Your account has been deactivated."}, status=200)

class HardDeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        reason = request.data.get("reason")

        if not reason:
            return Response({"error": "A reason is required."}, status=400)

        if user_has_financial_activity(user):
            return Response(
                {"error": "You cannot permanently delete your account while you have pending orders, unpaid payments, or incoming payouts."},
                status=400
            )

        hashed_id = hashlib.sha256(str(user.id).encode()).hexdigest()
        # ADDED (10-03-26)
        # Creates audit record
        DeletionAudit.from_user(user, reason)

        user.delete()

        return Response({"message": "Your account has been permanently deleted."}, status=200)
@api_view(["GET"])
@permission_classes([IsAdmin])
def failed_login_attempts_view(request):
    attempts = FailedLoginAttempt.objects.order_by("-timestamp")
    serializer = FailedLoginAttemptSerializer(attempts, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def deleted_accounts_view(request):
    audits = DeletionAudit.objects.order_by("-deleted_at")
    serializer = DeletionAuditSerializer(audits, many=True)
    return Response(serializer.data)