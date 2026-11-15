"""JWT cookies с безопасными ограничениями и автоматическим переизданием."""

from django.conf import settings


ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"


def set_auth_cookies(response, access: str, refresh: str | None = None):
    config = {
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "path": settings.AUTH_COOKIE_PATH,
    }
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        **config,
    )
    if refresh is not None:
        response.set_cookie(
            REFRESH_COOKIE,
            refresh,
            max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
            **config,
        )
    response["Cache-Control"] = "no-store"
    return response


def clear_auth_cookies(response):
    for key in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.delete_cookie(
            key,
            path=settings.AUTH_COOKIE_PATH,
            samesite=settings.AUTH_COOKIE_SAMESITE,
        )
    response["Cache-Control"] = "no-store"
    return response


class RotatedJWTCookieMiddleware:
    """Возвращает обновлённые cookies после безопасного авто-refresh в API."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        access = getattr(request, "_rotated_jwt_access", None)
        if access and response.status_code < 500:
            set_auth_cookies(
                response,
                access,
                getattr(request, "_rotated_jwt_refresh", None),
            )
        return response
