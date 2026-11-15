"""Автоматические проверки сигналов и консольных уведомлений ДЗ 21."""

from datetime import timedelta
from contextlib import redirect_stdout
from io import StringIO

from django.core import mail
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .models import SubTask, Task


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class TaskStatusEmailTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="task-owner",
            email="owner@example.test",
            password="Temporary!123456",
        )
        self.stranger = User.objects.create_user(
            username="stranger",
            email="stranger@example.test",
            password="Temporary!123456",
        )
        self.task = Task.objects.create(
            owner=self.owner,
            title="Task with notification",
            description="Initial description",
            deadline=timezone.now() + timedelta(days=7),
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.owner)

    def test_status_change_sends_one_mail_to_owner_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.api.patch(
                f"/api/tasks/{self.task.pk}/", {"status": "in_progress"}, format="json"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["owner@example.test"])
        self.assertIn("New", mail.outbox[0].body)
        self.assertIn("In progress", mail.outbox[0].body)
        self.assertIn(self.task.title, mail.outbox[0].body)

    def test_close_task_sends_mail_only_once(self):
        self.task.status = "done"
        with self.captureOnCommitCallbacks(execute=True) as first:
            self.task.save(update_fields=["status"])
        with self.captureOnCommitCallbacks(execute=True) as repeated:
            self.task.save(update_fields=["status"])
        self.assertEqual((len(first), len(repeated)), (1, 0))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("закрыта", mail.outbox[0].body)

    def test_no_mail_for_unchanged_status_or_other_fields(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.task.save()
            self.task.description = "Changed"
            self.task.save(update_fields=["description"])
            response = self.api.patch(
                f"/api/tasks/{self.task.pk}/", {"title": "New title"}, format="json"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(callbacks, [])
        self.assertEqual(mail.outbox, [])

    def test_status_not_in_update_fields_does_not_notify(self):
        self.task.status = "done"
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.task.save(update_fields=["description"])
        self.assertEqual(callbacks, [])
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "new")

    def test_two_real_transitions_send_two_distinct_messages(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.task.status = "pending"
            self.task.save(update_fields=["status"])
        with self.captureOnCommitCallbacks(execute=True):
            self.task.status = "done"
            self.task.save(update_fields=["status"])
            self.task.save(update_fields=["status"])
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("Pending", mail.outbox[0].body)
        self.assertIn("Done", mail.outbox[1].body)

    def test_new_task_creation_does_not_notify(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            Task.objects.create(
                owner=self.owner,
                title="Created without notification",
                description="New",
                deadline=timezone.now() + timedelta(days=7),
            )
        self.assertEqual(callbacks, [])
        self.assertEqual(mail.outbox, [])

    def test_subtasks_are_not_notified(self):
        subtask = SubTask.objects.create(
            task=self.task,
            owner=self.owner,
            title="Subtask email excluded",
            description="Subtask",
            deadline=timezone.now() + timedelta(days=7),
        )
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            subtask.status = "done"
            subtask.save(update_fields=["status"])
        self.assertEqual(callbacks, [])
        self.assertEqual(mail.outbox, [])

    def test_owner_without_email_does_not_notify(self):
        self.owner.email = ""
        self.owner.save(update_fields=["email"])
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.task.status = "blocked"
            self.task.save(update_fields=["status"])
        self.assertEqual(callbacks, [])
        self.assertEqual(mail.outbox, [])

    def test_task_without_owner_does_not_notify(self):
        orphan = Task.objects.create(
            title="Unowned task",
            description="Legacy",
            deadline=timezone.now() + timedelta(days=7),
        )
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            orphan.status = "done"
            orphan.save(update_fields=["status"])
        self.assertEqual(callbacks, [])
        self.assertEqual(mail.outbox, [])

    def test_rollback_does_not_send_mail(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            try:
                with transaction.atomic():
                    self.task.status = "done"
                    self.task.save(update_fields=["status"])
                    raise ValueError("Rollback deliberately")
            except ValueError:
                pass
        self.assertEqual(callbacks, [])
        self.assertEqual(mail.outbox, [])
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "new")

    def test_console_backend_prints_message(self):
        output = StringIO()
        with self.settings(
            EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"
        ):
            with redirect_stdout(output):
                with self.captureOnCommitCallbacks(execute=True):
                    self.task.status = "done"
                    self.task.save(update_fields=["status"])
        self.assertIn("To: owner@example.test", output.getvalue())
        self.assertIn("Задача закрыта.", output.getvalue())

    def test_other_user_cannot_change_task_or_trigger_notification(self):
        intruder = APIClient()
        intruder.force_authenticate(user=self.stranger)
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            result = intruder.patch(
                f"/api/tasks/{self.task.pk}/", {"status": "done"}, format="json"
            )
        self.assertEqual(result.status_code, 403)
        self.assertEqual(callbacks, [])
        self.assertEqual(mail.outbox, [])
