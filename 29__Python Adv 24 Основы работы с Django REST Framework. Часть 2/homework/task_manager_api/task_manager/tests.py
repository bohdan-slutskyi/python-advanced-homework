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
        self.assertEqual(len(response.data), 1)

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
