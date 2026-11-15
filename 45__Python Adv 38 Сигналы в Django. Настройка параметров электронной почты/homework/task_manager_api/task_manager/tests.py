from datetime import timedelta
import logging
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .models import Category, Task, SubTask


class TaskManagerJwtTests(APITestCase):
    def setUp(self):
        self.deadline = timezone.now() + timedelta(days=20)
        User = get_user_model()
        self.user = User.objects.create_user(username="student", password="PracticePass!234")
        self.staff = User.objects.create_user(
            username="teacher", password="PracticePass!234", is_staff=True
        )
        self.categories = [Category.objects.create(name=f"Category {i:02}") for i in range(13)]
        self.tasks = [
            Task.objects.create(title=f"Task {i:02}", description="Example", deadline=self.deadline)
            for i in range(13)
        ]
        SubTask.objects.bulk_create([
            SubTask(task=self.tasks[0], title=f"Subtask {i:02}",
                    description="Example", deadline=self.deadline)
            for i in range(13)
        ])
        self.tasks[0].categories.add(self.categories[0])

    def token_client(self, user: str) -> APIClient:
        response = self.client.post(
            "/api/token/",
            {"username": user, "password": "PracticePass!234"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        return client

    def test_obtain_and_refresh_jwt(self):
        response = self.client.post(
            "/api/token/",
            {"username": "student", "password": "PracticePass!234"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        refreshed = self.client.post(
            "/api/token/refresh/", {"refresh": response.data["refresh"]}, format="json"
        )
        self.assertEqual(refreshed.status_code, 200)
        self.assertIn("access", refreshed.data)
        self.assertEqual(
            self.client.post(
                "/api/token/", {"username": "student", "password": "wrong"}, format="json"
            ).status_code, 401
        )

    def test_authentication_and_permissions_on_all_api_views(self):
        student = self.token_client("student")
        teacher = self.token_client("teacher")
        task_path = f"/api/tasks/{self.tasks[0].pk}/"
        subtask_path = f"/api/subtasks/{SubTask.objects.first().pk}/"
        cases = [
            ("/api/tasks/", 401, 200),
            (task_path, 401, 200),
            ("/api/subtasks/", 401, 200),
            (subtask_path, 401, 200),
            ("/api/categories/", 200, 200),
            (f"/api/categories/{self.categories[0].pk}/", 200, 200),
            ("/api/categories/count-tasks/", 200, 200),
            (f"/api/categories/{self.categories[0].pk}/count-tasks/", 200, 200),
            ("/api/tasks/statistics/", 401, 403),
        ]
        for path, anonymous_status, student_status in cases:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, anonymous_status)
                self.assertEqual(student.get(path).status_code, student_status)
        self.assertEqual(teacher.get("/api/tasks/statistics/").status_code, 200)

    def test_all_task_changes_require_bearer(self):
        payload = {
            "title": "Created task", "description": "Text", "deadline": self.deadline.isoformat(),
        }
        self.assertEqual(self.client.post("/api/tasks/", payload, format="json").status_code, 401)
        self.assertEqual(
            self.client.patch(f"/api/tasks/{self.tasks[0].pk}/", {"status": "done"},
                              format="json").status_code, 401
        )
        self.assertEqual(self.client.delete(f"/api/tasks/{self.tasks[0].pk}/").status_code, 401)
        student = self.token_client("student")
        created = student.post("/api/tasks/", payload, format="json")
        self.assertEqual(created.status_code, 201)
        path = f"/api/tasks/{created.data['id']}/"
        self.assertEqual(student.patch(path, {"status": "done"}, format="json").status_code, 200)
        self.assertEqual(student.delete(path).status_code, 204)

    def test_category_read_public_write_protected(self):
        payload = {"name": "Special category"}
        self.assertEqual(self.client.post("/api/categories/", payload, format="json").status_code, 401)
        student = self.token_client("student")
        response = student.post("/api/categories/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        path = f"/api/categories/{response.data['id']}/"
        self.assertEqual(self.client.delete(path).status_code, 401)
        self.assertEqual(student.delete(path).status_code, 204)
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_refresh_and_invalid_access_token_do_not_bypass_permissions(self):
        self.assertEqual(
            self.client.get("/api/tasks/", HTTP_AUTHORIZATION="Bearer invalid").status_code, 401
        )
        pair = self.client.post(
            "/api/token/", {"username": "student", "password": "PracticePass!234"},
            format="json",
        ).data
        new_access = self.client.post(
            "/api/token/refresh/", {"refresh": pair["refresh"]}, format="json"
        ).data["access"]
        self.assertEqual(
            self.client.get("/api/tasks/", HTTP_AUTHORIZATION=f"Bearer {new_access}").status_code,
            200,
        )

    def test_global_page_size_five_and_navigation(self):
        student = self.token_client("student")
        for path in ["tasks", "subtasks", "categories", "categories/count-tasks"]:
            with self.subTest(path=path):
                first = student.get(f"/api/{path}/?page_size=100")
                self.assertEqual(first.status_code, 200)
                self.assertEqual(first.data["count"], 13)
                self.assertEqual(len(first.data["results"]), 5)
                self.assertIsNotNone(first.data["next"])
                seen = []
                response = first
                while True:
                    seen.extend(row["id"] for row in response.data["results"])
                    if not response.data["next"]:
                        break
                    url = urlsplit(response.data["next"])
                    response = student.get(url.path + "?" + url.query)
                    self.assertLessEqual(len(response.data["results"]), 5)
                self.assertEqual(len(seen), 13)
                self.assertEqual(len(set(seen)), 13)
                page_two = student.get(f"/api/{path}/?page=2")
                self.assertEqual(len(page_two.data["results"]), 5)
                page_three = student.get(f"/api/{path}/?page=3")
                self.assertEqual(len(page_three.data["results"]), 3)
                self.assertEqual(student.get(f"/api/{path}/?page=4").status_code, 404)

    def test_filters_crud_statistics_and_soft_delete(self):
        student = self.token_client("student")
        teacher = self.token_client("teacher")
        self.tasks[0].status = "done"
        self.tasks[0].save(update_fields=["status"])
        filtered = student.get("/api/tasks/", {
            "status": "done", "search": "Task 00", "deadline": self.deadline.isoformat()
        })
        self.assertEqual([item["id"] for item in filtered.data["results"]], [self.tasks[0].pk])
        asc = student.get("/api/tasks/?ordering=created_at").data["results"]
        desc = student.get("/api/tasks/?ordering=-created_at").data["results"]
        self.assertEqual(asc[0]["id"], self.tasks[0].pk)
        self.assertEqual(desc[0]["id"], self.tasks[-1].pk)
        self.assertEqual(teacher.get("/api/tasks/statistics/").data["total_tasks"], 13)
        path = f"/api/categories/{self.categories[0].pk}/"
        self.assertEqual(student.delete(path).status_code, 204)
        self.assertTrue(Category.all_objects.get(pk=self.categories[0].pk).is_deleted)
        self.assertTrue(Task.objects.filter(pk=self.tasks[0].pk).exists())

    def test_separate_logs_still_work(self):
        student = self.token_client("student")
        with self.settings(DEBUG=True):
            student.get("/api/tasks/")
            self.client.get("/api/missing/")
        for name in ["task_manager.http", "django.db.backends"]:
            for handler in logging.getLogger(name).handlers:
                handler.flush()
        http = (settings.LOGS_DIR / "http_logs.log").read_text()
        sql = (settings.LOGS_DIR / "db_logs.log").read_text()
        self.assertIn("GET /api/tasks/ 200", http)
        self.assertIn("GET /api/missing/ 404", http)
        self.assertIn("SELECT", sql)
        self.assertNotIn("SELECT", http)
        self.assertNotIn("GET /api/tasks/", sql)
