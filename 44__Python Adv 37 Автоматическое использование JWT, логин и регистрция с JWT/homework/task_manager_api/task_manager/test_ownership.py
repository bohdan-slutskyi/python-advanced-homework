from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .models import Task, SubTask


class OwnerPermissionsTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="owner_a", password="TestOnly!12345")
        self.bob = User.objects.create_user(username="owner_b", password="TestOnly!12345")
        self.deadline = (timezone.now() + timedelta(days=7)).isoformat()
        self.own_task = Task.objects.create(
            title="Owned by A", description="Private change",
            deadline=timezone.now() + timedelta(days=7), owner=self.alice,
        )
        self.other_task = Task.objects.create(
            title="Owned by B", description="Private change",
            deadline=timezone.now() + timedelta(days=7), owner=self.bob,
        )
        self.own_subtask = SubTask.objects.create(
            title="Subtask A", description="Private change", task=self.own_task,
            deadline=timezone.now() + timedelta(days=7), owner=self.alice,
        )

    def client_for(self, user):
        token = self.client.post("/api/token/", {
            "username": user.username, "password": "TestOnly!12345",
        }, format="json")
        self.assertEqual(token.status_code, 200)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")
        return client

    def test_jwt_creates_task_with_request_user_not_submitted_owner(self):
        api = self.client_for(self.alice)
        created = api.post("/api/tasks/", {
            "title": "A created task", "description": "New",
            "deadline": self.deadline, "owner": self.bob.pk,
        }, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["owner"], self.alice.pk)
        self.assertEqual(Task.objects.get(pk=created.data["id"]).owner, self.alice)

    def test_authenticated_user_sees_own_tasks_only_via_my_tasks(self):
        alice = self.client_for(self.alice)
        bob = self.client_for(self.bob)
        anonymous = self.client.get("/api/tasks/my/")
        self.assertEqual(anonymous.status_code, 401)
        list_a = alice.get("/api/tasks/my/")
        list_b = bob.get("/api/tasks/my/")
        self.assertEqual(list_a.status_code, 200)
        self.assertEqual([t["id"] for t in list_a.data["results"]], [self.own_task.pk])
        self.assertEqual([t["id"] for t in list_b.data["results"]], [self.other_task.pk])

    def test_task_owner_can_edit_and_delete_and_other_cannot(self):
        alice = self.client_for(self.alice)
        bob = self.client_for(self.bob)
        url = f"/api/tasks/{self.own_task.pk}/"
        self.assertEqual(bob.get(url).status_code, 200)  # IsOwnerOrReadOnly
        self.assertEqual(
            bob.patch(url, {"status": "done"}, format="json").status_code, 403
        )
        self.assertEqual(bob.delete(url).status_code, 403)
        change = alice.patch(url, {"description": "Changed by author", "owner": self.bob.pk}, format="json")
        self.assertEqual(change.status_code, 200, change.data)
        self.own_task.refresh_from_db()
        self.assertEqual(self.own_task.owner_id, self.alice.pk)
        self.assertEqual(self.own_task.description, "Changed by author")
        self.assertEqual(alice.delete(url).status_code, 204)

    def test_unauthenticated_write_denied(self):
        url = f"/api/tasks/{self.own_task.pk}/"
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.patch(url, {"status": "done"}, format="json").status_code, 401)
        self.assertEqual(self.client.delete(url).status_code, 401)

    def test_subtask_owner_and_relation_restrictions(self):
        alice = self.client_for(self.alice)
        bob = self.client_for(self.bob)
        path = f"/api/subtasks/{self.own_subtask.pk}/"
        self.assertEqual(bob.get(path).status_code, 200)
        self.assertEqual(bob.patch(path, {"title": "Intrusion"}, format="json").status_code, 403)
        self.assertEqual(bob.delete(path).status_code, 403)
        self.assertEqual(
            alice.patch(path, {"task": self.other_task.pk}, format="json").status_code,
            400,
        )
        accepted = alice.patch(
            path, {"title": "Changed by owner", "owner": self.bob.pk}, format="json"
        )
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.own_subtask.refresh_from_db()
        self.assertEqual(self.own_subtask.owner_id, self.alice.pk)
        self.assertEqual(self.own_subtask.title, "Changed by owner")
        self.assertEqual(alice.delete(path).status_code, 204)

    def test_subtask_created_for_owned_task_only(self):
        alice = self.client_for(self.alice)
        payload = {
            "title": "New subtask", "description": "Test",
            "deadline": self.deadline, "task": self.other_task.pk,
        }
        self.assertEqual(alice.post("/api/subtasks/", payload, format="json").status_code, 400)
        payload["task"] = self.own_task.pk
        payload["owner"] = self.bob.pk
        response = alice.post("/api/subtasks/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["owner"], self.alice.pk)
        self.assertEqual(SubTask.objects.get(pk=response.data["id"]).owner_id, self.alice.pk)

    def test_legacy_ownerless_tasks_cannot_be_modified_but_are_migratable(self):
        legacy = Task.objects.create(
            title="Legacy no owner", description="Migrated row",
            deadline=timezone.now() + timedelta(days=7),
        )
        alice = self.client_for(self.alice)
        self.assertEqual(alice.get(f"/api/tasks/{legacy.pk}/").status_code, 200)
        self.assertEqual(
            alice.patch(f"/api/tasks/{legacy.pk}/", {"status": "done"}, format="json").status_code,
            403,
        )
        self.assertNotIn(
            legacy.pk,
            [t["id"] for t in alice.get("/api/tasks/my/").data["results"]],
        )

    def test_swagger_and_redoc_routes_are_public(self):
        for path in ("/swagger/", "/redoc/", "/swagger.json"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, str(response.content[:220]))
        spec = self.client.get("/swagger.json").json()
        self.assertIn("/tasks/my/", spec["paths"])
        self.assertIn("/token/", spec["paths"])
        self.assertIn("Bearer", spec["securityDefinitions"])
