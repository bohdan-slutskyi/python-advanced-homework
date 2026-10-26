from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Category, SubTask, Task
from .serializers import (
    CategoryCreateSerializer,
    SubTaskCreateSerializer,
    TaskCreateSerializer,
    TaskDetailSerializer,
)


class SerializerHomeworkTests(APITestCase):
    def setUp(self):
        self.task = Task.objects.create(
            title="Prepare workshop",
            description="Prepare the workshop materials",
            deadline=timezone.now() + timedelta(days=2),
        )

    def test_subtask_created_at_is_read_only(self):
        serializer = SubTaskCreateSerializer(
            data={
                "title": "Collect references",
                "description": "Find reliable sources",
                "task": self.task.pk,
                "deadline": (timezone.now() + timedelta(days=1)).isoformat(),
                "created_at": "2000-01-01T00:00:00Z",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        subtask = serializer.save()
        self.assertGreater(subtask.created_at.year, 2000)
        self.assertTrue(serializer.fields["created_at"].read_only)

    def test_category_create_and_update_reject_duplicate_names(self):
        Category.objects.create(name="Planning")
        duplicate_create = CategoryCreateSerializer(data={"name": "Planning"})
        self.assertFalse(duplicate_create.is_valid())

        category = Category.objects.create(name="Research")
        duplicate_update = CategoryCreateSerializer(
            category,
            data={"name": "Planning"},
        )
        self.assertFalse(duplicate_update.is_valid())

    def test_category_can_keep_its_name_when_updated(self):
        category = Category.objects.create(name="Planning")
        serializer = CategoryCreateSerializer(category, data={"name": "Planning"})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.save().name, "Planning")

    def test_task_detail_contains_all_related_subtasks(self):
        SubTask.objects.create(
            title="Collect references",
            description="Find reliable sources",
            task=self.task,
            deadline=timezone.now() + timedelta(days=1),
        )
        data = TaskDetailSerializer(self.task).data
        self.assertEqual(len(data["subtasks"]), 1)
        self.assertEqual(data["subtasks"][0]["title"], "Collect references")

    def test_task_create_rejects_deadline_in_the_past(self):
        serializer = TaskCreateSerializer(
            data={
                "title": "Past deadline task",
                "description": "This deadline has passed",
                "deadline": (timezone.now() - timedelta(days=1)).isoformat(),
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("deadline", serializer.errors)


class SubTaskAPIViewTests(APITestCase):
    def setUp(self):
        self.task = Task.objects.create(
            title="Prepare workshop",
            description="Prepare the workshop materials",
            deadline=timezone.now() + timedelta(days=2),
        )
        self.subtask = SubTask.objects.create(
            title="Collect references",
            description="Find reliable sources",
            task=self.task,
            deadline=timezone.now() + timedelta(days=1),
        )

    def test_list_and_create_subtasks(self):
        response = self.client.get("/api/subtasks/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)

        response = self.client.post(
            "/api/subtasks/",
            {
                "title": "Draft outline",
                "description": "Create an initial outline",
                "task": self.task.pk,
                "deadline": (timezone.now() + timedelta(days=3)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(SubTask.objects.count(), 2)

    def test_retrieve_update_partial_update_and_delete(self):
        url = f"/api/subtasks/{self.subtask.pk}/"
        self.assertEqual(self.client.get(url).status_code, 200)

        put_response = self.client.put(
            url,
            {
                "title": "Collect updated references",
                "description": "Find and verify sources",
                "task": self.task.pk,
                "status": "in_progress",
                "deadline": (timezone.now() + timedelta(days=1)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(put_response.status_code, 200)

        patch_response = self.client.patch(
            url,
            {"status": "done"},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.data["status"], "done")

        delete_response = self.client.delete(url)
        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(SubTask.objects.filter(pk=self.subtask.pk).exists())

    def test_unknown_subtask_returns_not_found(self):
        response = self.client.get("/api/subtasks/999999/")
        self.assertEqual(response.status_code, 404)


class QueryParametersTests(APITestCase):
    def setUp(self):
        from datetime import datetime, timezone as dt_timezone
        self.task = Task.objects.create(
            title="Prepare presentation", description="Slides",
            deadline=datetime(2030, 1, 1, 12, tzinfo=dt_timezone.utc),
        )  # 1 января 2030 года — вторник.
        self.other_task = Task.objects.create(
            title="Prepare workshop", description="Workshop",
            deadline=datetime(2030, 1, 2, 12, tzinfo=dt_timezone.utc),
        )
        self.subtasks = []
        for number in range(7):
            subtask = SubTask.objects.create(
                title=f"Step {number}", description="Work item",
                task=self.task if number < 6 else self.other_task,
                status="done" if number % 2 == 0 else "new",
                deadline=self.task.deadline,
            )
            # Явные даты позволяют проверить сортировку независимо от скорости создания.
            SubTask.objects.filter(pk=subtask.pk).update(
                created_at=timezone.now() - timedelta(days=7 - number)
            )
            self.subtasks.append(subtask)

    def test_tasks_without_filter_include_every_task(self):
        response = self.client.get("/api/tasks/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({item["id"] for item in response.data}, {self.task.pk, self.other_task.pk})

    def test_weekday_accepts_russian_english_and_django_number(self):
        for weekday in ("вторник", "Tuesday", "3"):
            with self.subTest(weekday=weekday):
                response = self.client.get("/api/tasks/", {"weekday": weekday})
                self.assertEqual(response.status_code, 200)
                self.assertEqual([item["id"] for item in response.data], [self.task.pk])

    def test_invalid_weekday_returns_bad_request(self):
        for weekday in ("8", "0", "", "unknown"):
            with self.subTest(weekday=weekday):
                self.assertEqual(self.client.get("/api/tasks/", {"weekday": weekday}).status_code, 400)

    def test_default_pagination_and_newest_first_order(self):
        first = self.client.get("/api/subtasks/")
        second = self.client.get("/api/subtasks/", {"page": 2})
        self.assertEqual(first.data["count"], 7)
        self.assertEqual(len(first.data["results"]), 5)
        self.assertEqual(len(second.data["results"]), 2)
        ids = [item["id"] for item in first.data["results"] + second.data["results"]]
        self.assertEqual(ids, [item.pk for item in reversed(self.subtasks)])
        self.assertIsNotNone(first.data["next"])
        self.assertIsNone(second.data["next"])

    def test_page_size_cannot_increase_the_five_item_limit(self):
        response = self.client.get("/api/subtasks/", {"page_size": 100})
        self.assertEqual(len(response.data["results"]), 5)

    def test_filter_by_exact_parent_title_keeps_pagination(self):
        response = self.client.get("/api/subtasks/", {"task_title": self.task.title})
        self.assertEqual(response.data["count"], 6)
        self.assertEqual(len(response.data["results"]), 5)
        self.assertTrue(all(item["task"] == self.task.pk for item in response.data["results"]))

    def test_filter_by_status(self):
        response = self.client.get("/api/subtasks/", {"status": "done"})
        self.assertEqual(response.data["count"], 4)
        self.assertTrue(all(item["status"] == "done" for item in response.data["results"]))

    def test_both_filters_apply_together(self):
        response = self.client.get("/api/subtasks/", {"task_title": self.task.title, "status": "done"})
        self.assertEqual(response.data["count"], 3)
        self.assertTrue(all(item["task"] == self.task.pk and item["status"] == "done" for item in response.data["results"]))

    def test_unknown_parent_returns_empty_paginated_response(self):
        response = self.client.get("/api/subtasks/", {"task_title": "Unknown task"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])

    def test_invalid_status_and_missing_page(self):
        self.assertEqual(self.client.get("/api/subtasks/", {"status": "unknown"}).status_code, 400)
        self.assertEqual(self.client.get("/api/subtasks/", {"page": 99}).status_code, 404)
