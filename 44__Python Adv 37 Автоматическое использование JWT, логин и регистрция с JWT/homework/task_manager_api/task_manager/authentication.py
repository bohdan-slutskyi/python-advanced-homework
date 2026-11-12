"""JWT в заголовке Bearer или HttpOnly cookies, без обхода CSRF."""

from django.conf import settings
from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import SAFE_METHODS
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from .auth_cookies import ACCESS_COOKIE, REFRESH_COOKIE
from .models import RevokedAccessToken


class CookieOrHeaderJWTAuthentication(JWTAuthentication):
    """Header-based запросы совместимы с прошлым ДЗ; cookies требуют CSRF."""

    def get_validated_token(self, raw_token):
        token = super().get_validated_token(raw_token)
        if RevokedAccessToken.objects.filter(jti=token["jti"]).exists():
            raise AuthenticationFailed("Токен доступа отозван.")
        return token

    def authenticate(self, request):
        if self.get_header(request) is not None:
            return super().authenticate(request)

        raw_access = request.COOKIES.get(ACCESS_COOKIE)
        raw_refresh = request.COOKIES.get(REFRESH_COOKIE)
        if not raw_access and not raw_refresh:
            return None

        if request.method not in SAFE_METHODS:
            self.enforce_csrf(request)

        if raw_access:
            try:
                validated = self.get_validated_token(raw_access)
            except InvalidToken:
                # Для GET можно обновить истекший access без участия клиента.
                if request.method not in SAFE_METHODS or not raw_refresh:
                    raise
            else:
                return self.get_user(validated), validated

        if request.method not in SAFE_METHODS or not raw_refresh:
            return None

        # Автоматическая ротация refresh и обновление access на безопасном GET.
        serializer = TokenRefreshSerializer(data={"refresh": raw_refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except (InvalidToken, TokenError) as exc:
            raise AuthenticationFailed("Токен обновления недействителен.") from exc
        data = serializer.validated_data
        token = self.get_validated_token(data["access"])
        request._request._rotated_jwt_access = data["access"]
        request._request._rotated_jwt_refresh = data.get("refresh")
        return self.get_user(token), token

    @staticmethod
    def enforce_csrf(request):
        check = CSRFCheck(lambda request: None)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise PermissionDenied(f"CSRF validation failed: {reason}")
