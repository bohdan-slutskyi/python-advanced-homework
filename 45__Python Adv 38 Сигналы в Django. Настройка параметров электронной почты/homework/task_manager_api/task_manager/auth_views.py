"""Регистрация, вход, обновление и выход с HttpOnly JWT cookies."""

from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .auth_cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from .auth_serializers import LoginSerializer, RegisterSerializer
from .authentication import CookieOrHeaderJWTAuthentication
from .models import RevokedAccessToken


class CsrfTokenView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        get_token(request)
        return Response({"detail": "CSRF cookie создана."})


def issue_jwt_cookies(response, request, user):
    refresh = RefreshToken.for_user(user)
    get_token(request)
    return set_auth_cookies(response, str(refresh.access_token), str(refresh))


@method_decorator(csrf_protect, name="dispatch")
class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        response = Response(
            {"user": {"username": user.username, "email": user.email}},
            status=status.HTTP_201_CREATED,
        )
        return issue_jwt_cookies(response, request, user)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        response = Response({"user": {"username": user.username, "email": user.email}})
        return issue_jwt_cookies(response, request, user)


@method_decorator(csrf_protect, name="dispatch")
class RefreshCookieView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        refresh = request.COOKIES.get(REFRESH_COOKIE)
        if not refresh:
            return Response(
                {"detail": "Отсутствует refresh cookie."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        serializer = TokenRefreshSerializer(data={"refresh": refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except (InvalidToken, TokenError):
            response = Response(
                {"detail": "Refresh токен недействителен."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            return clear_auth_cookies(response)
        tokens = serializer.validated_data
        response = Response({"detail": "Access токен обновлён."})
        return set_auth_cookies(response, tokens["access"], tokens.get("refresh"))


@method_decorator(csrf_protect, name="dispatch")
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieOrHeaderJWTAuthentication]

    def post(self, request):
        token = request.auth
        if token is not None:
            RevokedAccessToken.objects.get_or_create(
                jti=token["jti"],
                defaults={
                    "expires_at": datetime.fromtimestamp(token["exp"], tz=timezone.utc)
                },
            )

        refresh_cookie = request.COOKIES.get(REFRESH_COOKIE)
        if refresh_cookie:
            try:
                refresh = RefreshToken(refresh_cookie)
                if str(refresh["user_id"]) == str(request.user.pk):
                    refresh.blacklist()
            except TokenError:
                pass  # Удаляем cookie даже если refresh уже истёк или отозван.

        response = Response(status=status.HTTP_204_NO_CONTENT)
        return clear_auth_cookies(response)
