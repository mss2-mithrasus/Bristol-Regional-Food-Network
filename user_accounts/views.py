from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import RegistrationSerializer, LoginSerializer
from .permissions import IsProducer, IsCustomer, IsAdmin
from .models import DeletionRequest
from django.utils import timezone


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

# Soft delete user account function
def soft_delete_user_account(user, reason: str, by_user=True):
    user.is_active = False
    user.deleted_at = timezone.now()
    user.reason_for_deleting = reason
    user.deleted_by_user = by_user
    user.save()

# Hard delete user account function
def create_deletion_request(user, reason: str):
    return DeletionRequest.objects.create(
        user=user,
        reason=reason,
        processed=False,
    )


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
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            tokens = serializer.validated_data
            user = tokens["user"]

            if user.role == "producer":
                homepage = "/producer/home/"
            elif user.role == "admin":
                homepage = "/admin/home/"
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
            return Response({"message": "Logged out successfully"}, status=status.HTTP_200_OK)
        except Exception:
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

# Soft delete

class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reason = request.data.get("reason", "No reason provided")
        soft_delete_user_account(request.user, reason)
        return Response(
            {"message": "Your account has been deactivated (soft deleted)."},
            status=status.HTTP_200_OK
        )

# Hard delete
class RequestDeletionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reason = request.data.get("reason", "")
        create_deletion_request(request.user, reason)
        return Response(
            {"message": "Your deletion request has been submitted to admin."},
            status=status.HTTP_200_OK
        )
