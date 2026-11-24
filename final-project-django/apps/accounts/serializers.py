from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, style={"input_type": "password"}
    )

    def validate_password(self, value):
        if not value.strip():
            raise serializers.ValidationError("Password cannot be blank.")
        return value

    class Meta:
        model = User
        fields = ["id", "email", "display_name", "password"]
        read_only_fields = ["id"]

    def validate_email(self, value):
        email = User.objects.normalize_email_address(value)
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )
        return email

    def validate(self, attrs):
        user = User(email=attrs["email"], display_name=attrs["display_name"])
        try:
            validate_password(attrs["password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                user = User.objects.create_user(**validated_data)
                group = Group.objects.get(name="Tenant")
                user.groups.add(group)
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"email": "An account with this email already exists."}
            ) from exc
        return user


class LoginSerializer(TokenObtainPairSerializer):
    """Use the password exactly as supplied, consistently with Django auth."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password"].trim_whitespace = False


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
