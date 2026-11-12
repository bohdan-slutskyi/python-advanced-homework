
"""Контрольная проверка полного цикла, без записи секретов и демоданных в БД."""

import os
import secrets

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.db import transaction
from rest_framework.test import APIClient


def check(response, status, title):
    assert response.status_code == status, (
        f"{title}: expected {status}, got {response.status_code}"
    )
    print(f"{title:52} HTTP {status}")


def main():
    name = "demo_" + secrets.token_hex(5)
    password = "Temporary" + secrets.token_hex(5) + "Aa1!"
    client = APIClient(enforce_csrf_checks=True)
    with transaction.atomic():
        check(client.get("/api/auth/csrf/"), 200, "GET   /api/auth/csrf/ (CSRF cookie)")
        def post(url, data):
            return client.post(
                url, data, format="json",
                HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
            )
        created = post("/api/register/", {
            "username": name, "email": name + "@example.test", "password": password
        })
        check(created, 201, "POST  /api/register/ (validated, hashed password)")
        assert all(created.cookies[k]["httponly"] for k in ("access_token", "refresh_token"))
        assert "access" not in created.data and "refresh" not in created.data
        print("Cookies: access+refresh = HttpOnly; token values not in JSON")
        check(client.get("/api/tasks/my/"), 200, "GET   /api/tasks/my/ (cookie authentication)")

        # Logout invalidates both token types, then login is possible again.
        first_access = client.cookies["access_token"].value
        check(post("/api/logout/", {}), 204, "POST  /api/logout/ (blacklist + cookie delete)")
        bearer = APIClient()
        bearer.credentials(HTTP_AUTHORIZATION=f"Bearer {first_access}")
        check(bearer.get("/api/tasks/my/"), 401, "GET   with revoked access token")
        check(post("/api/login/", {
            "username": name, "password": password
        }), 200, "POST  /api/login/ (new JWT cookies)")

        old_refresh = client.cookies["refresh_token"].value
        refreshed = post("/api/auth/refresh/", {})
        check(refreshed, 200, "POST  /api/auth/refresh/ (refresh rotation)")
        assert old_refresh != client.cookies["refresh_token"].value
        check(client.get("/api/tasks/my/"), 200, "GET   /api/tasks/my/ (refreshed access)")

        check(post("/api/logout/", {}), 204, "POST  /api/logout/ (final logout)")
        check(client.get("/api/tasks/my/"), 401, "GET   after logout (no active session)")
        transaction.set_rollback(True)

    print("RESULT: all runtime scenarios passed; temporary users/tokens rolled back")
    print("SECURITY: password, JWT and SECRET_KEY values were not printed")


if __name__ == "__main__":
    main()
