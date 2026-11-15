"""Локальная проверка API; не сохраняет тестовые аккаунты, пароли и токены."""

import os
import secrets
from datetime import timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient


def secure_client(user, secret):
    api = APIClient()
    response = api.post(
        "/api/token/", {"username": user.username, "password": secret}, format="json"
    )
    assert response.status_code == 200
    assert response.data.get("access")
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return api


def check_status(response, expected):
    assert response.status_code == expected, (
        f"Expected HTTP {expected}, got HTTP {response.status_code}"
    )


def main():
    User = get_user_model()
    nonce = secrets.token_hex(5)
    secret_a, secret_b = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    with transaction.atomic():
        alice = User.objects.create_user(username="owner_a_" + nonce, password=secret_a)
        bob = User.objects.create_user(username="owner_b_" + nonce, password=secret_b)
        client_a, client_b = secure_client(alice, secret_a), secure_client(bob, secret_b)
        body = {
            "title": "Proof task " + nonce,
            "description": "Owner is assigned from request.user",
            "owner": bob.pk,  # Проверка: клиент не может назначить другого владельца.
            "deadline": (timezone.now() + timedelta(days=10)).isoformat(),
        }
        created = client_a.post("/api/tasks/", body, format="json")
        check_status(created, 201)
        assert created.data["owner"] == alice.pk
        task_id = created.data["id"]
        print(f"POST /api/tasks/                      201  owner=request.user: OK")

        mine = client_a.get("/api/tasks/my/")
        check_status(mine, 200)
        assert task_id in [item["id"] for item in mine.data["results"]]
        not_mine = client_b.get("/api/tasks/my/")
        check_status(not_mine, 200)
        assert task_id not in [item["id"] for item in not_mine.data["results"]]
        print("GET  /api/tasks/my/                   200  only current user's tasks: OK")

        denied_update = client_b.patch(
            f"/api/tasks/{task_id}/", {"status": "done"}, format="json"
        )
        denied_delete = client_b.delete(f"/api/tasks/{task_id}/")
        check_status(denied_update, 403)
        check_status(denied_delete, 403)
        print("PATCH/DELETE another user's task   403/403  blocked: OK")

        own_update = client_a.patch(
            f"/api/tasks/{task_id}/", {"status": "done"}, format="json"
        )
        check_status(own_update, 200)
        assert own_update.data["owner"] == alice.pk
        print("PATCH own task                        200  permitted: OK")

        sub = client_a.post(
            "/api/subtasks/",
            {
                "title": "Proof subtask " + nonce,
                "description": "Owned",
                "task": task_id,
                "deadline": (timezone.now() + timedelta(days=10)).isoformat(),
            },
            format="json",
        )
        check_status(sub, 201)
        assert sub.data["owner"] == alice.pk
        denied_sub = client_b.delete(f"/api/subtasks/{sub.data['id']}/")
        check_status(denied_sub, 403)
        print("POST /api/subtasks/                   201  owner=request.user: OK")
        print("DELETE another user's subtask        403  blocked: OK")

        anonymous = APIClient().get("/api/tasks/my/")
        check_status(anonymous, 401)
        print("GET  /api/tasks/my/ without JWT      401  blocked: OK")

        for path in ("/swagger/", "/redoc/", "/swagger.json"):
            check_status(APIClient().get(path), 200)
        print("Swagger / Redoc / OpenAPI JSON        200  documentation: OK")

        transaction.set_rollback(True)  # Никаких тестовых аккаунтов/задач в базе.
    print("RESULT: 8 scenarios passed; demo accounts and tasks rolled back.")
    print("SECURITY: JWTs, passwords and secret keys were not printed.")


if __name__ == "__main__":
    main()
