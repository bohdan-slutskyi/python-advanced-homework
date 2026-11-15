"""Валидация регистрации и входа; пароль никогда не выдаётся в ответе."""

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(
        min_length=3, max_length=150, validators=[UnicodeUsernameValidator()]
    )
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_username(self, value):
        if get_user_model().objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Этот логин уже занят.")
        return value

    def validate_email(self, value):
        normalized = value.strip().lower()
        if get_user_model().objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("Этот email уже зарегистрирован.")
        return normalized

    def validate(self, attrs):
        password = attrs["password"]
        user = get_user_model()(
            username=attrs["username"],
            email=attrs["email"],
        )
        try:
            validate_password(password, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        # Минимальная сложность сверх стандартных Django validators.
        if not (
            any(x.islower() for x in password)
            and any(x.isupper() for x in password)
            and any(x.isdigit() for x in password)
            and any(not x.isalnum() for x in password)
        ):
            raise serializers.ValidationError(
                {"password": "Нужны прописная и строчная буквы, цифра и спецсимвол."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        return get_user_model().objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["username"],
            password=attrs["password"],
        )
        if user is None or not user.is_active:
            raise serializers.ValidationError({"detail": "Неверный логин или пароль."})
        attrs["user"] = user
        return attrs
