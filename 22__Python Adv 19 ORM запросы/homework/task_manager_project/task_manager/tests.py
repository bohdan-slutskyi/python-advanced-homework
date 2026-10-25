from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from .models import SubTask, Task
from .presentation_queries import (
    INFORMATION_TITLE, SLIDES_TITLE, TASK_TITLE,
    create_records, delete_records, read_new_tasks, read_overdue_done_subtasks, update_records,
)


class PresentationQueriesTests(TestCase):
    def setUp(self):
        self.reference = timezone.now()

    def other_task(self):
        return Task.objects.create(title="Another task", description="Keep this record", deadline=self.reference)

    def test_create_exact_fields_and_deadlines(self):
        task, information, slides = create_records(self.reference)
        expected = (
            (task, TASK_TITLE, "Prepare materials and slides for the presentation", 3),
            (information, INFORMATION_TITLE, "Find necessary information for the presentation", 2),
            (slides, SLIDES_TITLE, "Create presentation slides", 1),
        )
        for obj, title, description, days in expected:
            with self.subTest(title=title):
                obj.refresh_from_db()
                self.assertEqual(obj.title, title)
                self.assertEqual(obj.description, description)
                self.assertEqual(obj.status, "new")
                self.assertEqual(obj.get_status_display(), "New")
                self.assertEqual(obj.deadline, self.reference + timedelta(days=days))
        self.assertEqual(list(task.subtasks.order_by("deadline")), [slides, information])

    def test_read_new_and_overdue_done(self):
        task, information, slides = create_records(self.reference)
        other = self.other_task()
        self.assertEqual(list(read_new_tasks()), [task, other])
        self.assertEqual(list(read_overdue_done_subtasks(self.reference)), [])
        information.status = "done"
        information.deadline = self.reference - timedelta(seconds=1)
        information.save()
        slides.status = "done"
        slides.deadline = self.reference
        slides.save()
        self.assertEqual(list(read_overdue_done_subtasks(self.reference)), [information])
        slides.deadline = self.reference + timedelta(seconds=1)
        slides.save()
        self.assertEqual(list(read_overdue_done_subtasks(self.reference)), [information])

    def test_updates_persist_and_leave_other_fields(self):
        task, information, slides = create_records(self.reference)
        update_records(task, information, slides, self.reference)
        for obj in (task, information, slides):
            obj.refresh_from_db()
        self.assertEqual(task.status, "in_progress")
        self.assertEqual(task.get_status_display(), "In progress")
        self.assertEqual(task.deadline, self.reference + timedelta(days=3))
        self.assertEqual(information.deadline, self.reference - timedelta(days=2))
        self.assertEqual(information.status, "new")
        self.assertEqual(slides.description, "Create and format presentation slides")
        self.assertEqual(slides.deadline, self.reference + timedelta(days=1))

    def test_delete_cascades_and_preserves_unrelated_records(self):
        task, information, slides = create_records(self.reference)
        other = self.other_task()
        child = SubTask.objects.create(title="Keep this subtask", description="Keep", task=other, deadline=self.reference)
        ids = [information.pk, slides.pk]
        total, by_model = delete_records(task)
        self.assertEqual(total, 3)
        self.assertEqual(by_model, {"task_manager.SubTask": 2, "task_manager.Task": 1})
        self.assertFalse(SubTask.objects.filter(pk__in=ids).exists())
        self.assertEqual(Task.objects.get(), other)
        self.assertEqual(SubTask.objects.get(), child)

    def test_task_title_collision_does_not_modify_existing_task(self):
        task = Task.objects.create(title=TASK_TITLE, description="Existing content", deadline=self.reference)
        with self.assertRaises(CommandError):
            call_command("presentation_crud", stdout=StringIO())
        task.refresh_from_db()
        self.assertEqual(task.description, "Existing content")
        self.assertFalse(SubTask.objects.exists())

    def test_subtask_title_collision_does_not_create_task(self):
        other = self.other_task()
        child = SubTask.objects.create(title=SLIDES_TITLE, description="Keep", task=other, deadline=self.reference)
        with self.assertRaises(CommandError):
            call_command("presentation_crud", stdout=StringIO())
        self.assertFalse(Task.objects.filter(title=TASK_TITLE).exists())
        self.assertEqual(SubTask.objects.get(), child)

    def test_command_rolls_back_on_failure(self):
        with patch("task_manager.management.commands.presentation_crud.update_records", side_effect=RuntimeError("test failure")):
            with self.assertRaises(RuntimeError):
                call_command("presentation_crud", stdout=StringIO())
        self.assertFalse(Task.objects.exists())
        self.assertFalse(SubTask.objects.exists())

    def test_command_runs_twice_and_reports_all_stages(self):
        for _ in range(2):
            output = StringIO()
            call_command("presentation_crud", stdout=output)
            text = output.getvalue()
            for marker in ("1. CREATE", "2. READ", "3. UPDATE", "4. DELETE", "CRUD completed successfully."):
                self.assertIn(marker, text)
            self.assertIn("Remaining exercise records: Task=0, SubTask=0", text)
            self.assertFalse(Task.objects.exists())
            self.assertFalse(SubTask.objects.exists())
