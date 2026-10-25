from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from .models import Category, SubTask, Task


class ModelTests(TestCase):
    def setUp(self):
        self.task = Task.objects.create(title="Создать каталог", description="Описание", deadline=timezone.now() + timedelta(days=3))
        self.subtask = SubTask.objects.create(title="Описать поля", description="Описание", task=self.task, deadline=timezone.now() + timedelta(days=2))
        self.category = Category.objects.create(name="Разработка")

    def test_string_representations(self):
        self.assertEqual(str(self.task), self.task.title)
        self.assertEqual(str(self.subtask), self.subtask.title)
        self.assertEqual(str(self.category), self.category.name)

    def test_metadata_and_real_tables(self):
        for model, table, label in (
            (Task, "task_manager_task", "Task"),
            (SubTask, "task_manager_subtask", "SubTask"),
            (Category, "task_manager_category", "Category"),
        ):
            with self.subTest(model=model):
                self.assertEqual(model._meta.db_table, table)
                self.assertEqual(model._meta.verbose_name, label)
                self.assertIn(table, connection.introspection.table_names())
        self.assertEqual(Task._meta.ordering, ["-created_at"])
        self.assertEqual(SubTask._meta.ordering, ["-created_at"])

    def test_unique_fields_enforced_by_database(self):
        for model, fields in (
            (Task, {"title": self.task.title, "description": "Другое", "deadline": timezone.now()}),
            (SubTask, {"title": self.subtask.title, "description": "Другое", "deadline": timezone.now(), "task": self.task}),
            (Category, {"name": self.category.name}),
        ):
            with self.subTest(model=model), self.assertRaises(IntegrityError), transaction.atomic():
                model.objects.create(**fields)

    def test_newest_first(self):
        Task.objects.filter(pk=self.task.pk).update(created_at=timezone.now() - timedelta(days=1))
        newer = Task.objects.create(title="Проверить каталог", description="Описание", deadline=timezone.now())
        self.assertEqual(list(Task.objects.all()), [newer, self.task])
        SubTask.objects.filter(pk=self.subtask.pk).update(created_at=timezone.now() - timedelta(days=1))
        newer_subtask = SubTask.objects.create(title="Проверить поля", description="Описание", task=self.task, deadline=timezone.now())
        self.assertEqual(list(SubTask.objects.all()), [newer_subtask, self.subtask])

    def test_existing_relations_preserved(self):
        self.task.categories.add(self.category)
        self.assertEqual(self.category.tasks.get(), self.task)
        self.assertEqual(self.task.subtasks.get(), self.subtask)
        self.task.delete()
        self.assertFalse(SubTask.objects.exists())
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())


class AdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(username="test_admin", password=None)
        cls.category = Category.objects.create(name="Разработка")

    def setUp(self):
        self.client.force_login(self.user)

    def task_payload(self, title="Создать интерфейс"):
        return {
            "title": title, "description": "Описание интерфейса", "status": "new",
            "deadline_0": "2026-12-01", "deadline_1": "12:00:00",
            "categories": [self.category.pk], "_save": "Save",
        }

    def test_create_task_and_subtask_through_admin(self):
        response = self.client.post("/admin/task_manager/task/add/", self.task_payload())
        self.assertEqual(response.status_code, 302)
        task = Task.objects.get()
        self.assertEqual(list(task.categories.all()), [self.category])
        response = self.client.post("/admin/task_manager/subtask/add/", {
            "title": "Проверить форму", "description": "Описание", "task": task.pk, "status": "pending",
            "deadline_0": "2026-11-30", "deadline_1": "12:00:00", "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SubTask.objects.get().task, task)

    def test_create_category_and_duplicate_validation(self):
        response = self.client.post("/admin/task_manager/category/add/", {"name": "Проверка", "_save": "Save"})
        self.assertEqual(response.status_code, 302)
        response = self.client.post("/admin/task_manager/category/add/", {"name": "Проверка", "_save": "Save"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["adminform"].form.errors["name"])
        self.assertEqual(Category.objects.filter(name="Проверка").count(), 1)

    def test_duplicate_task_rejected_by_form(self):
        self.client.post("/admin/task_manager/task/add/", self.task_payload())
        response = self.client.post("/admin/task_manager/task/add/", self.task_payload())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["adminform"].form.errors["title"])
        self.assertEqual(Task.objects.count(), 1)

    def test_lists_search_filter_and_readonly_date(self):
        self.client.post("/admin/task_manager/task/add/", self.task_payload())
        Task.objects.create(title="Написать документацию", description="Описание", status="done", deadline=timezone.now())
        response = self.client.get("/admin/task_manager/task/", {"q": "интерфейс"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["cl"].result_count, 1)
        response = self.client.get("/admin/task_manager/task/", {"status__exact": "done"})
        self.assertEqual(response.context["cl"].result_count, 1)
        task = Task.objects.get(title="Создать интерфейс")
        response = self.client.get(f"/admin/task_manager/task/{task.pk}/change/")
        self.assertNotIn("created_at", response.context["adminform"].form.fields)
        for model in ("category", "subtask"):
            self.assertEqual(self.client.get(f"/admin/task_manager/{model}/").status_code, 200)

    def test_anonymous_cannot_access_admin(self):
        self.client.logout()
        response = self.client.get("/admin/task_manager/task/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)


class FixtureTests(TestCase):
    def test_restore_demo_without_credentials(self):
        call_command("loaddata", "fixtures/demo.json", stdout=StringIO())
        self.assertEqual(Category.objects.count(), 2)
        self.assertEqual(Task.objects.count(), 2)
        self.assertEqual(SubTask.objects.count(), 2)
        self.assertEqual(get_user_model().objects.count(), 0)
        self.assertTrue(Task.objects.get(title="Создать каталог книг").categories.exists())
        self.assertEqual(SubTask.objects.get(title="Описать модель книги").task.title, "Создать каталог книг")
