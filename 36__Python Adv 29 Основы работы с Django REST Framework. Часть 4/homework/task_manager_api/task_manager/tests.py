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


class GenericViewsTests(APITestCase):
    def setUp(self):
        self.deadline = timezone.now().replace(microsecond=0) + timedelta(days=10)
        self.task = Task.objects.create(title="Alpha", description="needle", status="new", deadline=self.deadline)
        self.other = Task.objects.create(title="Beta", description="other", status="done", deadline=self.deadline + timedelta(days=1))
        self.subtask = SubTask.objects.create(task=self.task, title="Alpha child", description="needle", status="new", deadline=self.deadline)
        self.other_subtask = SubTask.objects.create(task=self.other, title="Beta child", description="other", status="done", deadline=self.deadline + timedelta(days=1))
        for model, first, second in [(Task, self.task, self.other), (SubTask, self.subtask, self.other_subtask)]:
            model.objects.filter(pk=first.pk).update(created_at=self.deadline-timedelta(days=12))
            model.objects.filter(pk=second.pk).update(created_at=self.deadline-timedelta(days=11))

    def items(self, response):
        self.assertEqual(response.status_code, 200)
        return response.data["results"] if isinstance(response.data, dict) else response.data

    def test_filters_search_and_ordering_for_both_models(self):
        for path, first, second in [("tasks", self.task, self.other), ("subtasks", self.subtask, self.other_subtask)]:
            for params in [{"status": "new"}, {"deadline": self.deadline.isoformat()}, {"search": "needle"}, {"search": "Alpha"}, {"status": "new", "search": "needle", "deadline": self.deadline.isoformat()}]:
                with self.subTest(path=path, params=params):
                    self.assertEqual([x["id"] for x in self.items(self.client.get(f"/api/{path}/", params))], [first.pk])
            for ordering, ids in [("created_at", [first.pk, second.pk]), ("-created_at", [second.pk, first.pk])]:
                self.assertEqual([x["id"] for x in self.items(self.client.get(f"/api/{path}/", {"ordering": ordering}))], ids)
            for params in [{"status": "unknown"}, {"deadline": "wrong-date"}]:
                self.assertEqual(self.client.get(f"/api/{path}/", params).status_code, 400)
            self.assertEqual(self.items(self.client.get(f"/api/{path}/", {"search": "absent"})), [])

    def test_task_full_crud_and_readonly_timestamp(self):
        data = {"title": "CRUD", "description": "Example", "status": "new", "deadline": self.deadline.isoformat(), "created_at": "2000-01-01T00:00:00Z"}
        created = self.client.post("/api/tasks/", data, format="json")
        self.assertEqual(created.status_code, 201)
        pk = created.data["id"]
        self.assertNotEqual(Task.objects.get(pk=pk).created_at.year, 2000)
        url = f"/api/tasks/{pk}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        data["title"] = "Updated"
        self.assertEqual(self.client.put(url, data, format="json").status_code, 200)
        self.assertEqual(self.client.patch(url, {"status": "done"}, format="json").data["status"], "done")
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post("/api/tasks/", {}, format="json").status_code, 400)

    def test_statistics_contract(self):
        response = self.client.get("/api/tasks/statistics/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_tasks"], 2)
        self.assertEqual(response.data["tasks_by_status"]["new"], 1)
        self.assertEqual(response.data["tasks_by_status"]["done"], 1)
        self.assertEqual(response.data["overdue_tasks"], 0)

    def test_browsable_api_forms(self):
        for path in ["tasks", "subtasks"]:
            response = self.client.get(f"/api/{path}/", HTTP_ACCEPT="text/html")
            self.assertEqual(response.status_code, 200)


class CategoryViewSetTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Planning")
        self.empty = Category.objects.create(name="Empty")
        self.task = Task.objects.create(title="Prepare workshop", description="Materials", deadline=timezone.now()+timedelta(days=10))
        self.task.categories.add(self.category)

    def test_category_crud_and_field_protection(self):
        response = self.client.post("/api/categories/", {"name": "Research", "is_deleted": True, "deleted_at": "2000-01-01T00:00:00Z"}, format="json")
        self.assertEqual(response.status_code, 201)
        pk = response.data["id"]
        url = f"/api/categories/{pk}/"
        self.assertFalse(response.data["is_deleted"])
        self.assertIsNone(response.data["deleted_at"])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.put(url, {"name": "Development"}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(url, {"name": "Testing"}, format="json").data["name"], "Testing")
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(Category.objects.filter(pk=pk).exists())
        self.assertTrue(Category.all_objects.get(pk=pk).is_deleted)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_counts_for_all_categories_and_one_category(self):
        second = Task.objects.create(title="Other task", description="Other", deadline=timezone.now()+timedelta(days=10))
        second.categories.add(self.category, self.empty)
        response = self.client.get("/api/categories/count-tasks/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({x["id"]: x["tasks_count"] for x in response.data}, {self.category.pk: 2, self.empty.pk: 1})
        response = self.client.get(f"/api/categories/{self.category.pk}/count-tasks/")
        self.assertEqual(response.data["tasks_count"], 2)
        second.delete()
        self.assertEqual(self.client.get(f"/api/categories/{self.empty.pk}/count-tasks/").data["tasks_count"], 0)

    def test_delete_preserves_record_tasks_and_links(self):
        before = timezone.now()
        self.assertEqual(self.client.delete(f"/api/categories/{self.category.pk}/").status_code, 204)
        deleted = Category.all_objects.get(pk=self.category.pk)
        self.assertTrue(deleted.is_deleted)
        self.assertGreaterEqual(deleted.deleted_at, before)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())
        self.assertTrue(Task.categories.through.objects.filter(task_id=self.task.pk, category_id=self.category.pk).exists())
        self.assertEqual(list(self.task.categories.all()), [])
        self.assertEqual(self.client.get(f"/api/tasks/{self.task.pk}/").data["categories"], [])
        self.assertEqual(self.client.get(f"/api/categories/{self.category.pk}/count-tasks/").status_code, 404)
        self.assertEqual({x["id"] for x in self.client.get("/api/categories/").data}, {self.empty.pk})
        self.assertEqual({x["id"] for x in self.client.get("/api/categories/count-tasks/").data}, {self.empty.pk})

    def test_bulk_delete_is_soft(self):
        self.assertEqual(Category.objects.filter(pk=self.category.pk).delete()[0], 1)
        self.assertTrue(Category.all_objects.get(pk=self.category.pk).is_deleted)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_repeated_delete_preserves_timestamp(self):
        self.category.delete()
        first_time = self.category.deleted_at
        self.assertEqual(self.category.delete()[0], 0)
        self.category.refresh_from_db()
        self.assertEqual(self.category.deleted_at, first_time)
        self.assertEqual(self.client.delete(f"/api/categories/{self.category.pk}/").status_code, 404)

    def test_unique_name_includes_deleted_categories(self):
        self.category.delete()
        response = self.client.post("/api/categories/", {"name": "Planning"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.patch(f"/api/categories/{self.empty.pk}/", {"name": "Planning"}, format="json").status_code, 400)

    def test_task_category_assignment(self):
        data = {"title": "API task", "description": "Example", "deadline": (timezone.now()+timedelta(days=10)).isoformat(), "categories": [self.category.pk]}
        response = self.client.post("/api/tasks/", data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["categories"], [self.category.pk])
        self.category.delete()
        data["title"] = "Rejected task"
        self.assertEqual(self.client.post("/api/tasks/", data, format="json").status_code, 400)
        data["categories"] = [999999]
        self.assertEqual(self.client.post("/api/tasks/", data, format="json").status_code, 400)

    def test_empty_name_and_html(self):
        self.assertEqual(self.client.post("/api/categories/", {"name": ""}, format="json").status_code, 400)
        self.assertEqual(self.client.get("/api/categories/", HTTP_ACCEPT="text/html").status_code, 200)
