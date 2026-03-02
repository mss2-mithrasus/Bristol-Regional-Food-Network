from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

# Imports custom models created in models.py
from .models import (
    User, Person, Address,
    CustomerAccount, CommunityGroup, Restaurant,
    ProducerAccount
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

    def validate(self, data):
        # Checks if passwords match 
        if data["password"] != data["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match"})

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
            # If organisation status then account_type = community_group
            if validated_data.get("organisation_status"):
                account_type = "community"
            # If organisation name then account_type = restaurant
            elif validated_data.get("organisation_name"):
                account_type = "restaurant"
            # Otherwise it is a normal customer 
            else:
                account_type = "normal"
            
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
        user = authenticate(email=data["email"], password=data["password"])
        if not user:
            raise serializers.ValidationError({"error": "Invalid credentials"})
        # Stops user who have soft deleted their account from loggin in
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

        # JWT
        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": user,
        }