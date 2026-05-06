from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
import re, logging
# Imports custom models created in models.py
from .models import (
    User, Person, Address,
    CustomerAccount, CommunityGroup, Restaurant,
    ProducerAccount, FailedLoginAttempt, DeletionAudit
)


# REGISTRATION 
class RegistrationSerializer(serializers.Serializer):

    # User fields
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)
    role = serializers.CharField()

    # Person fields (individual customers + producer contacts)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)

    # Address fields
    address_line = serializers.CharField(required=False, allow_blank=True)
    postcode = serializers.CharField(required=False, allow_blank=True)

    # Community group fields
    organisation_name = serializers.CharField(required=False, allow_blank=True)
    organisation_status = serializers.CharField(required=False, allow_blank=True)

    # Producer fields
    business_name = serializers.CharField(required=False, allow_blank=True)
    contact_first_name = serializers.CharField(required=False, allow_blank=True)
    contact_last_name = serializers.CharField(required=False, allow_blank=True)

    # Added role 
    account_type = serializers.CharField(required=False, allow_blank=True)


    def validate(self, data):
        password = data["password"]
        password2 = data["password2"]

        # Checks if passwords match 
        if password != password2:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        # Custom password strength checker
        # Custom complexity
        # Checks if greater than 8 characters
        if len(password) < 8:
            raise serializers.ValidationError({"password": "Password must be at least 8 characters long."})

        # Checks if password included atleast one uppercase letter
        if not re.search(r"[A-Z]", password):
            raise serializers.ValidationError({"password": "Password must contain at least one uppercase letter."})
        
        # Checks if password included atleast one lowercase letter
        if not re.search(r"[a-z]", password):
            raise serializers.ValidationError({"password": "Password must contain at least one lowercase letter."})
        
        # Checks if password included atleast one number
        if not re.search(r"\d", password):
            raise serializers.ValidationError({"password": "Password must contain at least one number."})

        # Checks if password included atleast one special character
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise serializers.ValidationError({"password": "Password must contain at least one special character."})


        # Checks if password meets Django's password strenght requirements
        validate_password(data["password"])

        # Checks if the role is valid
        if data["role"] not in ["customer", "producer"]:
            raise serializers.ValidationError({"role": "Invalid role"})

        # Returns valid data 
        return data

    def create(self, validated_data):
        # Removes password and roles
        password = validated_data.pop("password")
        validated_data.pop("password2")
        role = validated_data.pop("role")
        account_type = validated_data.pop("account_type", "normal")

        # Create User
        user = User.objects.create(
            email=validated_data.get("email"),
            role=role,
        )
        user.set_password(password)
        user.save()

        # Create Address
        address = Address.objects.create(
            address_line=validated_data.get("address_line", ""),
            postcode=validated_data.get("postcode", "")
        )

        # CUSTOMER 
        if role == "customer":

            # Basic normal customer
            person = None
            if validated_data.get("first_name"):
                # Creates person object if first name exits 
                person = Person.objects.create(
                    user=user,
                    first_name=validated_data.get("first_name", ""),
                    last_name=validated_data.get("last_name", ""),
                    phone=validated_data.get("phone", "")
                )

            # Determine account type
            
            account_verified = True if account_type == "normal" else False



            # Create CustomerAccount
            customer = CustomerAccount.objects.create(
                user=user,
                person=person,
                address=address,
                account_type=account_type,
                accepted_terms=True,
                account_verified=account_verified
            )

            # Community group table
            if account_type == "community":
                CommunityGroup.objects.create(
                    customer_account=customer,
                    organisation_name=validated_data.get("organisation_name", ""),
                    organisation_status=validated_data.get("organisation_status", ""),
                    phone=validated_data.get("phone", "")
                )

            # Restaurant table
            if account_type == "restaurant":
                Restaurant.objects.create(
                    customer_account=customer,
                    organisation_name=validated_data.get("organisation_name", ""),
                    phone=validated_data.get("phone", "")
                )

        # PRODUCER FLOW
        if role == "producer":

            # Create contact person
            contact_person = Person.objects.create(
                user=user,
                first_name=validated_data.get("contact_first_name", ""),
                last_name=validated_data.get("contact_last_name", ""),
                phone=validated_data.get("phone", "")
            )

            # Create ProducerAccount
            ProducerAccount.objects.create(
                user=user,
                business_name=validated_data.get("business_name", ""),
                contact_person=contact_person,
                address=address,
                account_verified=False
            )

        return user



# LOGIN 
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        # Validates user login and checks credentials
        request = self.context.get("request")
        email = data["email"]
        password = data["password"]
        user = authenticate(email=email, password=password)
        if not user:
            FailedLoginAttempt.objects.create(
                email=email,
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", "")
            )
            raise serializers.ValidationError({"error": "Invalid credentials"})
        # Stops user who have soft deleted their account from logging in
        if not user.is_active:
            raise serializers.ValidationError({"error": "This account has been deactivated."})
        # Stops unverified producers from loggin in
        if user.role == "producer":
            if not hasattr(user, "produceraccount") or not user.produceraccount.account_verified:
                raise serializers.ValidationError({"error": "Producer account awaiting approval from admin."})
        # Stops unverified community group + resatarant from loggining in
        if user.role == "customer":
            acc = getattr(user, "customeraccount", None)
            if acc and acc.account_type in ["community", "restaurant"] and not acc.account_verified:
                raise serializers.ValidationError({"error": "Business account awaiting admin approval."})
        
        logger = logging.getLogger(__name__)
        logger.info(f"Successful login for {email} from {request.META.get('REMOTE_ADDR')}")


        # JWT
        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": user,
        }

class FailedLoginAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = FailedLoginAttempt
        fields = ["email", "ip_address", "user_agent", "timestamp"]


class DeletionAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeletionAudit
        fields = ["hashed_user_identifier", "role", "reason", "deleted_at"]
